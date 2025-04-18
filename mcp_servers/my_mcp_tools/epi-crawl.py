import os
import json
import time
import pymongo
import asyncio
import logging
import aiohttp
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timezone

load_dotenv()
mcp = FastMCP("epi-crawl")
TIME_NOW = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
TIMEGEP_SEC = 30

class FireCrawlRateLimitExceeded(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
    def __str__(self):
        return f"FireCrawlRateLimitExceeded: {self.message}"

class FireCrawl:
    def __init__(self, url):
        
        self.logger = logging.getLogger(__name__)
        self.FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
        self.FIRECRAWL_ENDPOINT = os.getenv('FIRECRAWL_ENDPOINT')
        self.url = url
        self.url_snap = url.split('/')[3] + ', ' + url.split('/')[-1].split('.')[0]
        
        self.payload = {
            "url": url,
            "scrapeOptions": {
                "formats": ["html"]
            }
        }
        
        self.headers = {
            "Authorization": f"Bearer {self.FIRECRAWL_API_KEY}",
            "Content-Type": "application/json"
        }
    
    def crawl(self) -> BeautifulSoup:
        
        #POST
        response = requests.request("POST", self.FIRECRAWL_ENDPOINT, json=self.payload, headers=self.headers) # type: ignore
        response_json = json.loads(response.text)
        
        while True:
            if response_json['success']:
                res_url = response_json['url']
                self.logger.info(f"Submitted: {self.url_snap};")
                break
            elif 'Rate limit exceeded' in response_json['error']:
                raise FireCrawlRateLimitExceeded(f"{response_json['error']}")
            else:
                self.logger.error(f"{self.url_snap}; {response_json['error']}, retrying in {TIMEGEP_SEC} seconds...")
                time.sleep(TIMEGEP_SEC)
        
        #GET
        while True:
            response = requests.request("GET", res_url, headers=self.headers)
            response_json = json.loads(response.text)
            if response_json['status'] == 'completed':
                self.logger.info(f"Completed: {self.url_snap};")
                break
            elif response_json['status'] == 'scraping':
                self.logger.info(f"Scraping: {self.url_snap};")
                time.sleep(TIMEGEP_SEC)
        soup = BeautifulSoup(response_json['data'][0]['html'], 'html.parser')
        return soup

    async def crawl_async(self, session) -> BeautifulSoup:
        
        # POST
        async with session.post(self.FIRECRAWL_ENDPOINT, json=self.payload, headers=self.headers) as response:
            response_json = await response.json()
            
            while True:
                if response_json['success']:
                    res_url = response_json['url'].replace("https:", self.FIRECRAWL_ENDPOINT.split('//')[0]) # type: ignore
                    self.logger.info(f"Submitted: {self.url_snap}")
                    break
                elif 'Rate limit exceeded' in response_json['error']:
                    raise Exception(f"{response_json['error']}")
                else:
                    self.logger.error(f"{self.url_snap}; {response_json['error']}, retrying in {TIMEGEP_SEC} seconds...")
                    time.sleep(TIMEGEP_SEC)

        # GET
        while True:
            async with session.get(res_url, headers=self.headers) as response:
                response_json = await response.json()
                if response_json['status'] == 'completed':
                    self.logger.info(f"Completed: {self.url_snap}; {response_json['status']}")
                    break
                elif response_json['status'] == 'scraping':
                    self.logger.info(f"Scraping: {self.url_snap}, retrying in {TIMEGEP_SEC} seconds...")
                    await asyncio.sleep(TIMEGEP_SEC)
        soup = BeautifulSoup(response_json['data'][0]['html'], 'html.parser')
        return soup

@mcp.tool()
async def crawl_2_url(url_1, url_2):
    async with aiohttp.ClientSession() as session:
        tasks = [FireCrawl(url).crawl_async(session) for url in [url_1, url_2]]
        soup_list = await asyncio.gather(*tasks)
    return soup_list

@mcp.tool()
async def get_us_epidata():
    
    url_us = {
        'all_respiratory_viruses': {
            'summary': 'https://www.cdc.gov/respiratory-viruses/data/activity-levels.html',
            'trends': 'https://www.cdc.gov/respiratory-viruses/data/activity-levels.html'
        },
        'clinical_cov': {
            'trends': 'same with all_respiratory_viruses > trends > COVID-19_percent_of_tests_positive',
            'variants': 'https://covid.cdc.gov/covid-data-tracker/#variant-proportions'
        },
        'wastewater_cov': {
            'trends': 'https://www.cdc.gov/nwss/rv/COVID19-nationaltrend.html',
            'variants': 'https://www.cdc.gov/nwss/rv/COVID19-variants.html'
        }
    }

    ## all_respiratory_viruses & clinical_cov trends
    arv_soup = FireCrawl(url_us['all_respiratory_viruses']['summary']).crawl()
    arv_summary_str = arv_soup.find('div', class_='update-snapshot').text.strip() # type: ignore
    arv_summary = [
        {
        'date': str(datetime.strptime(arv_summary_str[35:56], '%A, %B %d, %Y').replace(tzinfo=timezone.utc)),
        'virus_type': 'all respiratory viruses',
        'summary': arv_summary_str
        }
    ]
    arv_trends  = []
    cc_cov_trends = []
    for row in arv_soup.find_all('div', class_='table-container')[-1].find('tbody').find_all('tr'): # type: ignore
        cells = row.find_all('td') # type: ignore
        arv_trends_td = {
            'date': str(datetime.strptime(cells[0].text.strip(), '%B %d, %Y').replace(tzinfo=timezone.utc)),
            'virus_type': 'all respiratory viruses',
            'COVID-19_percent_of_tests_positive': float(cells[1].text.strip()),
            'Influenza_percent_of_tests_positive': float(cells[2].text.strip()),
            'RSV_percent_of_tests_positive': float(cells[3].text.strip())
        }
        cov_td = {
            'date': str(datetime.strptime(cells[0].text.strip(), '%B %d, %Y').replace(tzinfo=timezone.utc)),
            'virus_type': 'COVID-19',
            'COVID-19_percent_of_tests_positive': float(cells[1].text.strip())
        }
        arv_trends.append(arv_trends_td)
        cc_cov_trends.append(cov_td)
        
    time.sleep(TIMEGEP_SEC)
    
    ## clinical_cov variants
    cc_cov_variants_soup = FireCrawl(url_us['clinical_cov']['variants']).crawl()
    cc_cov_raw_soup = cc_cov_variants_soup.select('#circulatingVariants')[0]
    cc_cov_variants_list = cc_cov_raw_soup.find_all('div', class_ = 'tab-vizHeaderWrapper')
    cc_cov_variant_name = cc_cov_variants_list[7:24]
    cc_cov_variant_ratio = cc_cov_variants_list[41:58]
    cc_cov_variants = [
        {
        'date': str(datetime.strptime(cc_cov_variants_list[-1].text, '%m/%d/%y').replace(tzinfo=timezone.utc)),
        'virus_type': 'COVID-19',
        'percentage': ';'.join([f"{voc.text}:{float(ratio.text[:-1])/100:.2f}" for voc, ratio in zip(cc_cov_variant_name, cc_cov_variant_ratio)])
        }
    ]
    time.sleep(TIMEGEP_SEC)
    
    ## wastewater_cov
    ww_cov_soup_list = await crawl_2_url(url_us['wastewater_cov']['trends'], url_us['wastewater_cov']['variants'])
    ww_cov_trends = []
    for row in ww_cov_soup_list[0].find('div', class_='table-container').find('tbody').find_all('tr'):
        cov_td = {
            'date': str(datetime.strptime(row.find('td').text.strip(), '%m/%d/%y').replace(tzinfo=timezone.utc)),
            'virus_type': 'COVID-19',
            'COVID-19_NWSS_wastewater_viral_activity_levels': float(row.find_all('td')[1].text.strip())
        }
        ww_cov_trends.append(cov_td)
    time.sleep(TIMEGEP_SEC)

    ww_cov_variants = []
    ww_cov_variants_soup = ww_cov_soup_list[1].find('div', class_='table-container')
    ww_cov_variants_name = [i.text.split('Press')[0].strip() for i in ww_cov_variants_soup.find('thead').find_all('th')]
    ww_cov_variants_name[0] = 'Date'
    for row in ww_cov_variants_soup.find('tbody').find_all('tr'):
        cells = row.find_all('td')
        ww_cov_var = dict(zip(ww_cov_variants_name, [i.text.strip() for i in cells]))
        ww_cov_td = {
            'date': str(datetime.strptime(ww_cov_var['Date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)),
            'virus_type': 'COVID-19',
            'percentage': ';'.join([f"{voc}:{float(partio[:-1])/100:.2f}" for voc, partio in ww_cov_var.items() if voc != 'Date' and partio != 'N/A'])
        }
        ww_cov_variants.append(ww_cov_td)
    time.sleep(TIMEGEP_SEC)

    epi_us = {
        'all_respiratory_viruses': {
            'summary': arv_summary,
            'trends': arv_trends
        },
        'clinical_cov': {
            'trends': cc_cov_trends,
            'variants': cc_cov_variants
        },
        'wastewater_cov': {
            'trends': ww_cov_trends,
            'variants': ww_cov_variants
        }
    }
    os.makedirs('history') if not os.path.exists('history') else None
    with open(f'history/data_us_history_{TIME_NOW}.json', 'w') as f:
        json.dump(epi_us, f, indent=4)
    
    epi_us_recent = {
        'all_respiratory_viruses': {
            'summary': arv_summary,
            'trends': arv_trends[0:10]
        },
        'clinical_cov': {
            'trends': cc_cov_trends[0:10],
            'variants': cc_cov_variants[0:10]
        },
        'wastewater_cov': {
            'trends': ww_cov_trends[0:10],
            'variants': ww_cov_variants[0:10]
        }
    }
    os.makedirs('recent') if not os.path.exists('recent') else None
    with open(f'recent/data_us_recent_{TIME_NOW}.json', 'w') as f:
        json.dump(epi_us_recent, f, indent=4)
    
    return epi_us, epi_us_recent

@mcp.tool()
def update_db(epi_us, epi_us_recent):
    
    update_record_list = []
    logger = logging.getLogger(__name__)
    MONGO_CLIENT = pymongo.MongoClient("mongodb://10.20.17.14:27017/")
    MONGO_DB = MONGO_CLIENT["epi-crawl"]
    
    def update(head, db):
        d_head = datetime.strptime(head['date'], '%Y-%m-%d %H:%M:%S%z')
        for i in db.find().sort('date', pymongo.DESCENDING).limit(1):
            d_db = i['date'].replace(tzinfo=timezone.utc)
        if d_head > d_db:
            document = head
            document['date'] = d_head
            db.insert_one(document)
            logger.info(f'🌟 update {db.name}: {str(d_db)[:10]} -> {str(d_head)[:10]}')
            return document
        else:
            logger.info(f'🏖️ no update {db.name}: {str(d_db)[:10]} -> {str(d_head)[:10]}')
            return None
    
    for head, db in zip(
        [
            epi_us['all_respiratory_viruses']['summary'][0],
            epi_us['all_respiratory_viruses']['trends'][0],
            epi_us['clinical_cov']['trends'][0],
            epi_us['clinical_cov']['variants'][0],
            epi_us['wastewater_cov']['trends'][0],
            epi_us['wastewater_cov']['variants'][0],
        ],
        [
            MONGO_DB.all_respiratory_viruses_summary,
            MONGO_DB.all_respiratory_viruses_trends,
            MONGO_DB.clinical_cov_trends,
            MONGO_DB.clinical_cov_variants,
            MONGO_DB.wastewater_cov_trends,
            MONGO_DB.wastewater_cov_variants
        ]
    ):
        update_record = update(head, db)
        if update_record is not None:
            update_record_list.append(update_record)
    if len(update_record_list) == 0:
        logger.info('🏖️ no update')
        return
    else:
        MONGO_DB.recent_shortcasts.insert_one({
            "date": datetime.strptime(epi_us_recent["all_respiratory_viruses"]["summary"][0]["date"], '%Y-%m-%d %H:%M:%S%z').replace(tzinfo=timezone.utc),
            "recent": epi_us_recent
        })
        logger.info(f'🌟 update recent_shortcasts: {str(epi_us_recent["all_respiratory_viruses"]["summary"][0]["date"])[:10]}')

    MONGO_CLIENT.close()
    logger.info(f"Total Updated {len(update_record_list)} items.")
    logger.info(f"✅ epi-crawl updated successfully, next update in 3 days...")
    
    return

if __name__ == "__main__":
    
    ## if using MCP, uncomment the following line, and comment the rest line, and run: uv run epi-crawl.py
    mcp.run(transport='stdio')

    ## if not using MCP, uncomment the following line, and comment the above line, and run: python epi-crawl.py or uv run epi-crawl.py
    # async def main():
    #     while True:
    #         try:
    #             epi_us, epi_us_recent = await get_us_epidata()
    #             update_db(epi_us, epi_us_recent)
    #             time.sleep(3600 * 24 * 3)
    #         except FireCrawlRateLimitExceeded as e:
    #             print(e)
    #             print('⚠️ FireCrawl Rate limit exceeded, retrying in 60 seconds...')
    #             time.sleep(60)
    #         except:
    #             print('⚠️ An error occurred, retrying in 10 seconds...')
    #             time.sleep(10)

    # asyncio.run(main())
