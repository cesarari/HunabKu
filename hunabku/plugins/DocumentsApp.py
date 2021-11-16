from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from bson import ObjectId
from pymongo import ASCENDING,DESCENDING
from pickle import load

class DocumentsApp(HunabkuPluginBase):
    def __init__(self, hunabku):
        super().__init__(hunabku)

    def get_info(self,idx):
        document = self.colav_db['documents'].find_one({"_id":ObjectId(idx)})
        if document:
            entry={"id":document["_id"],
                "title":document["titles"][0]["title"],
                "abstract":document["abstract"],
                "source":{},
                "year_published":document["year_published"],
                "language":document["languages"][0] if len(document["languages"])>0 else "",
                "volume":document["volume"],
                "issue":document["issue"],
                "authors":[],
                "open_access_status":document["open_access_status"],
                "citations_count":document["citations_count"],
                "external_ids":[],
                "external_urls":document["urls"]
            }

            source=self.colav_db["sources"].find_one({"_id":document["source"]["id"]})
            entry_source={
                "name":source["title"],
                "serials":{}
            }
            for serial in source["serials"]:
                if not serial["type"] in entry_source.keys():
                    entry_source["serials"][serial["type"]]=serial["value"]
            entry["source"]=entry_source

            for author in document["authors"]:
                author_entry={
                    "corresponding":author["corresponding"]
                }
                auth_reg=self.colav_db["authors"].find_one({"_id":author["id"]})
                author_entry["name"]=auth_reg["full_name"]
                author_entry["id"]=auth_reg["_id"]
                author_entry["affiliations"]=[]
                for aff in author["affiliations"]:
                    aff_reg=self.colav_db["institutions"].find_one({"_id":aff["id"]})
                    author_entry["affiliations"].append({"name":aff_reg["name"],"id":aff_reg["_id"]})

                entry["authors"].append(author_entry)
            
            for ext in document["external_ids"]:
                if ext["source"]=="doi":
                    entry["external_ids"].append({
                        "id":ext["id"],
                        "source":"doi",
                        "url":"https://doi.org/"+ext["id"]
                        
                    })
                if ext["source"]=="lens":
                    entry["external_ids"].append({
                        "id":ext["id"],
                        "source":"lens",
                        "url":"https://www.lens.org/lens/scholar/article/"+ext["id"]
                    })
                if ext["source"]=="scholar":
                    entry["external_ids"].append({
                        "id":ext["id"],
                        "source":"scholar",
                        "url":"https://scholar.google.com/scholar?hl=en&as_sdt=0%2C5&q=info%3A"+ext["id"]+
                            "%3Ascholar.google.com"
                    })    
            
            return {"data":entry,"filters":{}}
        else:
            return None

    def get_networks(self,idx=None,max_results=100,page=1,start_year=None,end_year=None,sort=None,direction=None):
        entry={
            "citations_network":{"nodes":load(open("./nodes.p","rb")),"edges":load(open("./edges.p","rb"))},
            "citations":[{}]
        }

        return {"data":entry,"filters":{}}

    @endpoint('/app/documents', methods=['GET'])
    def app_document(self):
        """
        @api {get} /app/documents Document
        @apiName app
        @apiGroup CoLav app
        @apiDescription Responds with information about the document

        @apiParam {String} apikey Credential for authentication
        @apiParam {String} data (info,networks) Whether is the general information or the production
        @apiParam {Object} id The mongodb id of the document requested

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 204) msg  The HTTP 204 No Content.
        @apiError (Error 200) msg  The HTTP 200 OK.

        @apiSuccessExample {json} Success-Response (data=info):
            {
                "id": "602ef785728ecc2d8e62d4ed",
                "title": "Histology of the Reticuloendothelial System of the Spleen in Mice of Inbred Strains",
                "abstract": "The histologic structure of the reticuloendothelial system of the spleen of mice of inbred strains was studied with a silver impregnation technique. The reticuloendothelial cells in the spleen form a general pattern common to all strains of mice examined. A central structure is formed by parallel rows of fibers and reticuloendothelial cells disposed around the follicular artery. Distributed throughout the follicle are scattered reticuloendothelial cells. At the periphery of the follicle the reticuloendothelial cells form a collar surrounding it. In the space between the collar and the red pulp is an area filled with sinusoids and a few reticuloendothelial cells. This space stains lightly with silver, appearing as a halo around the follicles. In the red pulp, the reticuloendothelial cells do not form geometric patterns as they do in the follicles. The morphological structure and arrangement of the reticuloendothelium are characteristic for each strain of inbred mice examined. The differences by which the strains are distinguished depend on the pattern of the reticuloendothelium in the splenic follicles. No quantitative difference was detected and the number of cells appeared to be roughly equivalent in all strains. Susceptibility to spontaneous tumor development could not be correlated with the structural differences found, though in strains highly susceptible to the development of leukemia the germinal centers of the splenic follicles were prominent, and their reticuloendothelial cells were abundant and large. © 1965, Oxford University Press.",
                "source": {
                    "name": "Journal of the National Cancer Institute",
                    "serials": {
                    "unknown": "00278874",
                    "eissn": "14602105"
                    }
                },
                "year_published": 1965,
                "language": "en",
                "volume": "35",
                "issue": "1",
                "authors": [
                    {
                    "corresponding": true,
                    "name": "Oscar Duque",
                    "id": "602ef785728ecc2d8e62d4ec",
                    "affiliations": [
                        {
                        "name": "University of Antioquia",
                        "id": "60120afa4749273de6161883"
                        },
                        {
                        "name": "United States",
                        "id": "602ef785728ecc2d8e62d4eb"
                        }
                    ]
                    }
                ],
                "open_access_status": "closed",
                "citations_count": 5,
                "external_ids": [
                    {
                    "source": "lens",
                    "id": "146-769-885-695-441"
                    },
                    {
                    "source": "doi",
                    "id": "10.1093/jnci/35.1.15"
                    },
                    {
                    "source": "magid",
                    "id": "2142043866"
                    },
                    {
                    "source": "pmid",
                    "id": "5317934"
                    },
                    {
                    "source": "scopus",
                    "id": "2-s2.0-76549138821"
                    },
                    {
                    "source": "scholar",
                    "id": "GeY3wqc1_DgJ"
                    }
                ],
                "external_urls": [
                    {
                    "source": "scopus",
                    "url": "https://www.scopus.com/inward/record.uri?eid=2-s2.0-76549138821&doi=10.1093%2fjnci%2f35.1.15&partnerID=40&md5=fb4eec8a2f93b23a82746c827556f6d7"
                    }
                ]
                }
        """
        data = self.request.args.get('data')

        if data=="info":
            idx = self.request.args.get('id')
            info = self.get_info(idx)
            if info:    
                response = self.app.response_class(
                response=self.json.dumps(info),
                status=200,
                mimetype='application/json'
                )
            else:
                response = self.app.response_class(
                response=self.json.dumps({"status":"Request returned empty"}),
                status=204,
                mimetype='application/json'
            )
        elif data=="networks":
            idx = self.request.args.get('id')
            network=self.get_networks(idx)
            if network:
                response = self.app.response_class(
                response=self.json.dumps(network),
                status=200,
                mimetype='application/json'
                )
            else:
                response = self.app.response_class(
                response=self.json.dumps({"status":"Request returned empty"}),
                status=204,
                mimetype='application/json'
                )
        else:
            response = self.app.response_class(
                response=self.json.dumps({}),
                status=400,
                mimetype='application/json'
            )

        response.headers.add("Access-Control-Allow-Origin", "*")
        return response

