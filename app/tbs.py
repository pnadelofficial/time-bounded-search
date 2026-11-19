import re
from collections import defaultdict
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import pandas as pd
from pandas._libs.tslibs.parsing import DateParseError
import numpy as np
from sentence_transformers import SentenceTransformer
from pprint import pprint
import json
from tqdm import tqdm

color_mapping = {
    RGBColor(0xed, 0x7d, 0x31): "Activist or disease-related groups, organizations",
    RGBColor(0xee, 0x00, 0x00): "Concerning haemophiliacs",
    RGBColor(0xda, 0x73, 0x26): "Activist or disease-related groups, organizations",
    RGBColor(0x20, 0x25, 0xe8): "Campaigns, Compensation/payments",
    RGBColor(0x44, 0x72, 0xc4): "Campaigns, Compensation/payments",
    RGBColor(0xc0, 0x00, 0x00): "HIV/AIDS issues",
    RGBColor(0xc1, 0x15, 0x11): "HIV/AIDS issues",
    RGBColor(0x17, 0x2e, 0xdb): "Campaigns, Compensation/payments",
    RGBColor(0xc4, 0x59, 0x11): "Activist or disease-related groups, organizations",
    RGBColor(0xff, 0xc0, 0x00): "Activist or disease-related groups, organizations",
    RGBColor(0x00, 0x80, 0x00): "Treatments",
    WD_COLOR_INDEX.YELLOW: "Specific reference to hepatitis C, or people infected with HCV",
    RGBColor(0x00, 0x00, 0x00): "No topic",
    RGBColor(0xcc, 0x00, 0x99): "Legal cases, Trials and Settlements and Public Inquiries",
    RGBColor(0x00, 0x76, 0x35): "Treatments",
    RGBColor(0x05, 0xff, 0x76): "Science",
    RGBColor(0x00, 0x99, 0xff): "Event - not compensation",
    RGBColor(0x5c, 0xa2, 0xee): "Event - not compensation",
    RGBColor(0x21, 0x06, 0xe8): "Campaigns, Compensation/payments",
    RGBColor(0x37, 0x46, 0xd1): "Campaigns, Compensation/payments",
    RGBColor(0x2e, 0x13, 0xf9): "Campaigns, Compensation/payments",
    RGBColor(0x33, 0xcc, 0xcc): "Non-haemophiliacs with HIV, usually regarding payments or compensation",
    RGBColor(0x00, 0xb0, 0xf0): "Event - not compensation",
    WD_COLOR_INDEX.TURQUOISE: "Press",
    RGBColor(0x2f, 0xff, 0x8d): "Science",
    RGBColor(0xb1, 0x25, 0xa7): "Legal cases, Trials and Settlements and Public Inquiries",
    RGBColor(0x0f, 0x4d, 0xb1): "Campaigns, Compensation/payments",
    RGBColor(0x00, 0x86, 0x3d): "Treatments",
    RGBColor(0x00, 0x70, 0xc0): "Campaigns, Compensation/payments",
    RGBColor(0x00, 0x00, 0xff): "Campaigns, Compensation/payments",
    WD_COLOR_INDEX.PINK: "Other countries' HCV scandals/Inquiries",
    RGBColor(0x00, 0x33, 0xcc): "Campaigns, Compensation/payments",
    RGBColor(0x66, 0xff, 0xcc): "Non-haemophiliacs with HIV, usually regarding payments or compensation",
    RGBColor(0x00, 0xb0, 0x50): "Treatments",
    RGBColor(0x00, 0xff, 0x99): "Science", 
    RGBColor(0x21, 0x4b, 0xff): "Campaigns, Compensation/payments",
    RGBColor(0x06, 0x30, 0xe0): "Campaigns, Compensation/payments",
    RGBColor(0xff, 0x00, 0x00): "Concerning haemophiliacs",
    RGBColor(0xff, 0x21, 0x21): "Concerning haemophiliacs",
    RGBColor(0x8a, 0x21, 0xab): "Legal cases, Trials and Settlements and Public Inquiries",
    RGBColor(0x70, 0xad, 0x47): "Treatments",
    RGBColor(0x0e, 0x51, 0xe8): "Campaigns, Compensation/payments",
    RGBColor(0x48, 0xb8, 0xab): "Non-haemophiliacs with HIV, usually regarding payments or compensation",
    
}

thresholds = {
    "Activist or disease-related groups, organizations": 3,
    "Non-haemophiliacs with HIV, usually regarding payments or compensation": 3,
    "Campaigns, Compensation/payments": 1,
    "Treatments": 6,
    "Legal cases, Trials and Settlements and Public Inquiries": 1,
    "Science": 12,
    "Other countries' HCV scandals/Inquiries": 12,
    "Concerning haemophiliacs": 1,
    "Press": 1,
    "HIV/AIDS issues": 1,
    "Event - not compensation": 1,
    "No topic": 3,
    "Non-haemophiliacs with HIV, usually regarding payments or compensation": 3,
    'Specific reference to hepatitis C, or people infected with HCV': 3
}

months = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)'
date_pattern = r'\b(?:' \
    rf'\d{{1,2}}\s+{months}\s+\d{{4}}|' \
    rf'{months}\s+\d{{1,2}},?\s+\d{{4}}|' \
    r'(?:Early|Mid|Late)\s+\d{4}s?|' \
    rf'{months}\s+\d{{4}}' \
    r')\b'

class TimeTable:
    def __init__(self, word_path, date_re):
        self.word_path = word_path
        self.date_re = date_re

        self.doc = Document(word_path)
        self.bullets = self.extract_only_bullets(self.doc)
        self.grouped, self.topics = self.group_bullets_by_date_dict(self.bullets)
    
    def extract_only_bullets(self, doc):
        bullet_points = []
        
        for paragraph in doc.paragraphs:
            pPr = paragraph._element.pPr
            
            if pPr is not None:
                numPr = pPr.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr')
                
                if numPr is not None:
                    # Get the numId
                    numId = numPr.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numId')
                    
                    if numId is not None:
                        num_id = numId.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                        
                        # Check if it's a bullet (not numbered)
                        if self.is_bullet_list(doc, num_id):
                            topics_incom = {color_mapping[run.font.color.rgb] for run in paragraph.runs if run.font.color.rgb is not None and run.font.color.rgb != RGBColor(0x12, 0x12, 0x12)}
                            rest_topics = {color_mapping[run.font.highlight_color] for run in paragraph.runs if run.font.highlight_color is not None}
                            
                            if rest_topics == {None}:
                                topics = topics_incom
                            else:
                                topics = topics_incom | rest_topics
                                topics.discard(None) 
                            bullet_points.append((paragraph.text, topics))
        print("Colors all passing")
        return bullet_points

    def is_bullet_list(self, doc, num_id):
        """Check if a numbering ID corresponds to a bullet list"""
        try:
            numbering_part = doc.part.numbering_part
            numbering_xml = numbering_part.element
            
            # Find the num element with this numId
            num = numbering_xml.find(f'.//{{{numbering_xml.nsmap["w"]}}}num[@{{{numbering_xml.nsmap["w"]}}}numId="{num_id}"]')
            
            if num is not None:
                # Get the abstractNumId
                abstractNumId = num.find(f'.//{{{numbering_xml.nsmap["w"]}}}abstractNumId')
                abstract_num_id = abstractNumId.get(f'{{{numbering_xml.nsmap["w"]}}}val')
                
                # Find the abstractNum definition
                abstractNum = numbering_xml.find(f'.//{{{numbering_xml.nsmap["w"]}}}abstractNum[@{{{numbering_xml.nsmap["w"]}}}abstractNumId="{abstract_num_id}"]')
                
                if abstractNum is not None:
                    # Check the first level's numFmt
                    lvl = abstractNum.find(f'.//{{{numbering_xml.nsmap["w"]}}}lvl[@{{{numbering_xml.nsmap["w"]}}}ilvl="0"]')
                    numFmt = lvl.find(f'.//{{{numbering_xml.nsmap["w"]}}}numFmt')
                    
                    # Bullet lists use 'bullet' format, numbered use 'decimal', 'lowerLetter', etc.
                    fmt_val = numFmt.get(f'{{{numbering_xml.nsmap["w"]}}}val')
                    return fmt_val == 'bullet'
        except Exception as e:
            pass
        
        return False
    
    def extract_date(self, text):
        """Extract the date string from text"""
        match = re.search(date_pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
        return None

    def remove_date(self, text, date_str):
        """Remove the date from the text and clean up extra whitespace"""
        cleaned = text.replace(date_str, '').strip()
        # Clean up any double spaces or extra punctuation left behind
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'^\s*[-:]\s*', '', cleaned)  # Remove leading dash or colon
        return cleaned

    def group_bullets_by_date_dict(self, bullet_list):
        """Create dictionary with dates as keys and associated text as values"""
        date_dict = defaultdict(list)
        topic_dict = {}
        current_date = None
        
        for bullet in bullet_list:
            text, topics = bullet
            date_str = self.extract_date(text)
            
            if date_str:
                i = 1
                # This bullet has a date - start a new entry
                current_date = date_str
                # Remove date from text and make it the first element
                text_without_date = self.remove_date(text, date_str)
                date_dict[f"{current_date}_{i}"].append(text_without_date)
                topic_dict[f"{current_date}_{i}"] = topics
            else:
                # This bullet doesn't have a date - start a new entry appended with i
                if current_date:
                    i += 1
                    date_dict[f"{current_date}_{i}"].append(text)
                    topic_dict[f"{current_date}_{i}"] = topics
        
        return dict(date_dict), topic_dict

def inverse_square(days_diff, max_days=365*2):
    normalized_diff = days_diff / max_days
    return 1 / (1 + normalized_diff ** 2)

class TimeBoundedSearch:
    def __init__(self, df, timetable, model=None):
        self.df = df
        self.model = model
        self.sent_sim_template = "task: sentence similarity | query: {content}"
        self.timetable = timetable
        self.grouped = self.timetable.grouped
        self.topcis = self.timetable.topics
    
    def scale_score(self, sim_scores, item_dates, target_date, scaler_func, date_weight):
        sim_scores = np.array(sim_scores)
        days_diffs = np.abs(np.array([(target_date - d).days for d in item_dates]))
        date_scores = np.array([scaler_func(d) for d in days_diffs])
        composite = (1 - date_weight) * sim_scores + date_weight * date_scores
        return composite, date_scores
    
    def handle_ambiguous_dates(self, date_str):
        year = re.findall(r"(\d{4})", date_str)[0]
        if "Late" in date_str:
            year = int(year)+6
            new_date_str = f"1/1/{year}"
        elif "Early" in date_str:
            new_date_str = f"1/1/{year}"

        return pd.to_datetime(new_date_str)
    
    def time_bounded_search(self, date_key_from_timetable, month_threshold=2, go_backwards=True, precomputed_embeddings=None, scale_fn=inverse_square, date_weight=0.5, sim_threshold=.75, newspaper=None):
        if newspaper:
            df = self.df[self.df.Newspaper == newspaper]
            print(f"Filtered dataframe to {len(df)} documents from newspaper: {newspaper}")
        else:
            df = self.df
        associated_text = self.grouped[date_key_from_timetable]
        # some keys have multiple events
        query_embedding = self.model.encode(self.sent_sim_template.format(content=associated_text))

        date_key_from_timetable = date_key_from_timetable.split("_")[0]
        try:
            key_dt = pd.to_datetime(date_key_from_timetable)
        except DateParseError as e:
            print(f"Failed to parse: {date_key_from_timetable}")
            key_dt = self.handle_ambiguous_dates(date_key_from_timetable)

        buffer = pd.DateOffset(months=month_threshold)

        if go_backwards:
            zone_of_interest = df[
                (df.Date >= key_dt - buffer) & # backward looking
                (df.Date <= key_dt + buffer)   # forward looking
            ]
        else:   
            zone_of_interest = df[
                (df.Date >= key_dt) &          # backward looking
                (df.Date <= key_dt + buffer)   # forward looking
            ]

        if len(zone_of_interest) == 0:
            print("No results found.")
            return []

        print(f"Processing {len(zone_of_interest)} documents in the zone of interest...")
        if precomputed_embeddings is not None:
            zone_ids = zone_of_interest.index
            doc_embeddings = precomputed_embeddings[zone_ids]
            print(len(doc_embeddings))
        else:
            doc_texts = [t.Title + "\n" + t.chunks for t in zone_of_interest.itertuples()]
            doc_embeddings = self.model.encode([self.sent_sim_template.format(content=text) for text in doc_texts], show_progress_bar=True, device="mps")
        sim_scores = doc_embeddings @ query_embedding.T
        composite, _ = self.scale_score(sim_scores, zone_of_interest.Date, key_dt, scale_fn, date_weight)

        results = []
        for i in composite.argsort()[::-1]:
            score = composite[i]
            if score >= sim_threshold:
                results.append(zone_of_interest.iloc[i].to_dict())
        print(f"Final length of results: {len(results)}")
        return results

def report_result(results, date_key_from_timetable, grouped, topics):
    print("-"*40)
    print(f"Date from timetable: {date_key_from_timetable}")
    pprint(grouped[date_key_from_timetable])
    pprint(f"Topics: {topics[date_key_from_timetable]}")
    if len(results) == 0:
        print(f"No results found for {date_key_from_timetable}")
        print("-"*40)
        return
    print("-"*40)
    print(f"Found {len(results)} results")
    print("Text from timetable:")
    for i in range(len(results)):
        print(f"**Relevant Article {i+1}**")
        print(f"Title: {results[i]['Title']}")
        print(f"Date: {results[i]['Date']}")
        print(f"Newspaper: {results[i]['Newspaper']}")
        pprint(f"{results[i]['chunks']}")
        print("-"*40)

def main():
    timetable = TimeTable("Timetable-REV7 Hypotheses re press coverage of Hepatitis C in UK +color coding.docx", date_pattern)

    df = pd.read_csv("./all_ratings811.csv")
    def parse_date(val):
        for fmt in ('%Y-%m-%d', '%B %d, %Y'):
            try:
                return pd.to_datetime(val, format=fmt)
            except (ValueError, TypeError) as e:
                continue
        return pd.NaT  # fallback if nothing matches

    df['Date'] = df['Date'].apply(lambda x: x.replace(" 00:00:00", "").split("_")[0]).apply(parse_date)
    df = df[["Title", "Date", "Author", "Newspaper", "Source", "newspaper_type", "chunks"]]

    model = SentenceTransformer("/Users/pnadel01/models/fp/google_embeddinggemma-300m", device="mps")
    precomputed_embeddings = np.load('doc-embeddings811.npy')
    tbs = TimeBoundedSearch(df, timetable, model=model)
    
    results_by_date_key = {}
    for date_key in tqdm(list(timetable.grouped.keys()), total=len(timetable.grouped)):
        results = tbs.time_bounded_search(
            date_key_from_timetable=date_key, 
            month_threshold=sum([thresholds[t] for t in timetable.topics[date_key]])//len(timetable.topics[date_key]) if len(timetable.topics[date_key]) > 0 else 3, # vary by category: specific events should be smaller, more vague (drugs coming out) should be larger
            go_backwards=True, 
            precomputed_embeddings=precomputed_embeddings, 
            scale_fn=inverse_square, 
            date_weight=0.5, 
            sim_threshold=.75, # see month_threshold 
            newspaper=None
        )
        results_by_date_key[(date_key)] = results
    
    with open("tbs_results1020.json", "w") as json_file:
        json.dump(results_by_date_key, json_file, default=str, indent=4)
    return results_by_date_key

if __name__ == "__main__":
    main()