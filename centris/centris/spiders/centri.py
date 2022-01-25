import selectors
from unicodedata import category
import incremental
import scrapy
from scrapy import Selector
from scrapy_splash import SplashRequest
import json


class CentriSpider(scrapy.Spider):
    name = 'centri'
    allowed_domains = ['www.centris.ca']
    # start_urls = ['http://www.centris.ca/']
    position = {
        'startPosition': 0
    }

    script = '''
            function main(splash, args)
            assert(splash:go(args.url))
            assert(splash:wait(2))
            return {
                html = splash:html(),
            }
            end
    '''

    def start_requests(self):

        yield scrapy.Request(
            url="https://www.centris.ca/UserContext/Lock",
            method="POST",
            body=json.dumps({'uc': 0}),
            headers={
                'Content-Type': 'application/json',
            },
            callback=self.generate_uck

        )

    def generate_uck(self, response):
        r = response.body
        uck = str(r, "utf-8").strip()
        print(uck)
        query = {"query": {"UseGeographyShapes": 0, "Filters": [{"MatchType": "CityDistrictAll", "Text": "Montréal (All boroughs)", "Id": 5}], "FieldsValues": [{"fieldId": "CityDistrictAll", "value": 5, "fieldConditionId": "", "valueConditionId": ""}, {"fieldId": "Category", "value": "Residential", "fieldConditionId": "", "valueConditionId": ""}, {"fieldId": "SellingType", "value": "Rent", "fieldConditionId": "", "valueConditionId": ""}, {
            "fieldId": "LandArea", "value": "SquareFeet", "fieldConditionId": "IsLandArea", "valueConditionId": ""}, {"fieldId": "RentPrice", "value": 0, "fieldConditionId": "ForRent", "valueConditionId": ""}, {"fieldId": "RentPrice", "value": 1500, "fieldConditionId": "ForRent", "valueConditionId": ""}]}, "isHomePage": True}

        yield scrapy.Request(
            url="https://www.centris.ca/property/UpdateQuery",
            method='POST',
            body=json.dumps(query),
            headers={
                'Content-Type': 'application/json',
                'x-centris-uc': 0,
                'x-centris-uck': uck,
                'x-requested-with': 'XMLHttpRequest',

            },
            callback=self.update_query
        )

    def update_query(self, response):
        yield scrapy.Request(
            url='https://www.centris.ca/Property/GetInscriptions',
            method='POST',
            body=json.dumps(self.position),
            headers={
                'Content-Type': 'application/json'
            },
            callback=self.parse
        )

    def parse(self, response):
        resp_dict = json.loads(response.body)
        html = resp_dict.get('d').get('Result').get('html')
        sel = Selector(text=html)
        listings = sel.xpath(
            "//div[@class='property-thumbnail-item thumbnailItem col-12 col-sm-6 col-md-4 col-lg-3']")

        for listing in listings:
            summary = listing.xpath(
                ".//div[@class='shell']/div/a[@class='property-thumbnail-summary-link']/@href").get()
            summary = summary.replace('fr', 'en')
            summary_url = f'https://www.centris.ca{summary}'

            yield SplashRequest(

                url=summary_url,
                endpoint='execute',
                callback=self.parse_summary,
                args={
                    'lua_source': self.script
                },
                meta={
                    'url': summary_url,
                }

            )
        count = resp_dict.get('d').get('Result').get('count')
        increment_number = resp_dict.get('d').get(
            'Result').get('inscNumberPerPage')
        if self.position['startPosition'] < count:
            self.position['startPosition'] += increment_number
            yield scrapy.Request(
                url='https://www.centris.ca/Property/GetInscriptions',
                method='POST',
                body=json.dumps(self.position),
                headers={
                    'Content-Type': 'application/json'
                },
                callback=self.parse
            )

    def parse_summary(self, response):
        category = response.xpath("//span[@data-id='PageTitle']/text()").get()
        rooms = response.xpath(
            "normalize-space(//div[@class='col-lg-3 col-sm-6 piece']/text())").get()
        bedrooms = response.xpath(
            "normalize-space(//div[@class='col-lg-3 col-sm-6 cac']/text())").get()
        bathrooms = response.xpath(
            "normalize-space(//div[@class='col-lg-3 col-sm-6 sdb']/text())").get()
        price = response.xpath(
            "(//span[@class='text-nowrap'])[2]/text()").get()
        address = response.xpath("(//h2[@itemprop='address'])[1]/text()").get()
        description = response.xpath(
            "normalize-space(//div[@itemprop='description']/text())").get()
        url = response.request.meta['url']

        yield {
            'category': category,
            'url': url,
            'rooms': rooms,
            'bedrooms': bedrooms,
            'bathrooms': bathrooms,
            'price': price,
            'address': address,
            'description': description,
        }
