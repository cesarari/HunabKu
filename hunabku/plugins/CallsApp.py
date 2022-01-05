from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from bson import ObjectId
from pymongo import ASCENDING,DESCENDING
import requests
import json
from bs4 import BeautifulSoup
from dateutil import parser
import html_to_json


class CallsApp(HunabkuPluginBase):
    def __init__(self, hunabku):
        super().__init__(hunabku)

    def search_nih(self,max_results=100,page=1):


        if not page:
            page=1
        else:
            try:
                page=int(page)
            except:
                print("Could not convert end page to int")
                return None
        if not max_results:
            max_results=100
        else:
            try:
                max_results=int(max_results)
            except:
                print("Could not convert end max to int")
                return None

        skip = (page - 1)*max_results

        url='https://search.grants.nih.gov/guide/api/data?perpage=%d&sort=expdate:desc&from=%d&type=active,activenosis&parentic=all&primaryic=all&activitycodes=all&doctype=all&parentfoa=all&daterange=01021991-12132021&clinicaltrials=all&fields=all&spons=true&query='%(max_results,skip)

        
        response = requests.get(url)
        results = json.loads(response.text)

        calls = []
        total = results["data"]["hits"]["total"]

        for item in results["data"]["hits"]["hits"]:

            title=item.get("_source")["title"]
            if "Notice" in title:
                url = "https://grants.nih.gov/grants/guide/notice-files/"+item.get("_source")["docnum"]+".html"
            else:
                url = "https://grants.nih.gov/grants/guide/pa-files/"+item.get("_source")["docnum"]+".html"

            org=item.get("_source")["organization"]["primary"]
            exp_date = parser.parse(item.get("_source")["expdate"]).strftime("%Y-%m-%d")
            rel_date = parser.parse(item.get("_source")["reldate"]).strftime("%Y-%m-%d")
            


            entry = {"title":title,"organization":org,"expiration_date":exp_date,"release_date":rel_date,
                "url":url}

            calls.append(entry)




        return {"total":total,"page":page,"data":calls}
    
    def search_min(self,page=1):



        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="96"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Referer': 'https://minciencias.gov.co/convocatorias-asctei?order=body&sort=asc',
            'Accept-Language': 'es-419,es;q=0.9',
            'If-None-Match': '"1639931969-0"',
        }

        params = (
            ('order', 'field_fecha_de_apertura'),
            ('sort', 'asc'),
            ('page', '1'),
        )


        response = requests.get('https://minciencias.gov.co/convocatorias-asctei?order=field_fecha_de_apertura&sort=asc', headers=headers, params=params,verify=False)

        soup = BeautifulSoup(response.text,'lxml')

        box = soup.find_all('tr',class_='odd')
        calls_odd = []
        for e in box:
            try: 
                
                entry={}

                title=e.find('td',class_='views-field-title')
                cuantia = e.find('td',class_='views-field-field-cuantia-xl')
                apertura=e.find('td',class_='views-field-field-fecha-de-apertura')
                fecha=apertura.find('span',class_='date-display-single')

                url = "https://minciencias.gov.co/"+title.find('a')['href']

                entry['title']=title.get_text().replace("\n","").strip()
                entry['start']=fecha["content"]
                entry['amount']=cuantia.get_text().replace("\n","").strip()
                entry['link']=url

                calls_odd.append(entry)

            except:
                continue
        box = soup.find_all('tr',class_='even')
        calls_even = []
        for e in box:
            try: 
                
                entry={}

                title=e.find('td',class_='views-field-title')
                cuantia = e.find('td',class_='views-field-field-cuantia-xl')
                apertura=e.find('td',class_='views-field-field-fecha-de-apertura')
                fecha=apertura.find('span',class_='date-display-single')

                url = "https://minciencias.gov.co/"+title.find('a')['href']

                entry['title']=title.get_text().replace("\n","").strip()
                entry['start']=fecha["content"]
                entry['amount']=cuantia.get_text().replace("\n","").strip()
                entry['link']=url

                calls_even.append(entry)

            except:
                continue
        
        calls=[]
        for i in range(max([len(calls_odd),len(calls_even)])):
            if i<len(calls_odd):
                calls.append(calls_odd[i])
            if i<len(calls_even):
                calls.append(calls_even[i])


        return {"data":calls}
        
    
    @endpoint('/app/calls', methods=['GET'])
    def calls_search(self):
        """

        """
        data = self.request.args.get('data')

        if data=="nih":
            max_results=self.request.args.get('max') if 'max' in self.request.args else 10
            page=self.request.args.get('page') if 'page' in self.request.args else 1
            result = self.search_nih(max_results=max_results,page=page)
        elif data=="min":
            page=self.request.args.get('page') if 'page' in self.request.args else 1
            result = self.search_min(page=page)
        else:
            result=None

        if result:
            response = self.app.response_class(
            response=self.json.dumps(result),
            status=200,
            mimetype='application/json'
            )
        else:
            response = self.app.response_class(
            response=self.json.dumps({}),
            status=204,
            mimetype='application/json'
            )
        
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response