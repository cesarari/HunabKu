from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from bson import ObjectId
from pymongo import ASCENDING,DESCENDING

class SearchApp(HunabkuPluginBase):
    def __init__(self, hunabku):
        super().__init__(hunabku)

    def search_author(self,keywords="",affiliation="",country="",max_results=100,page=1):

        if keywords:
            cursor=self.colav_db['authors'].find({"$text":{"$search":keywords},"external_ids":{"$ne":[]}},{ "score": { "$meta": "textScore" } }).sort([("score", { "$meta": "textScore" } )])
            pipeline=[{"$match":{"$text":{"$search":keywords},"external_ids":{"$ne":[]}}}]
            aff_pipeline=[
                {"$match":{"$text":{"$search":keywords},"external_ids":{"$ne":[]}}},
                {"$unwind":"$affiliations"},{"$project":{"affiliations":1}},
                {"$group":{"_id":"$id","affiliation":{"$last":"$affiliations"}}},
                {"$group":{"_id":"$affiliation"}}
            ]
        else:
            cursor=self.colav_db['authors'].find({"external_ids":{"$ne":[]}})
            pipeline=[{"$match":{"external_ids":{"$ne":[]}}}]
            aff_pipeline=[
                {"$match":{"external_ids":{"$ne":[]}}},
                {"$unwind":"$affiliations"},{"$project":{"affiliations":1}},
                {"$group":{"_id":"$id","affiliation":{"$last":"$affiliations"}}},
                {"$group":{"_id":"$affiliation"}}
            ]

        affiliations=[reg["_id"] for reg in self.colav_db["authors"].aggregate(aff_pipeline) if "_id" in reg.keys()]

        countries=[]
        country_list=[]
        pipeline.extend([
            {"$unwind":"$affiliations"},
            {"$lookup":{
                "from":"institutions",
                "localField":"affiliations.id",
                "foreignField":"_id",
                "as":"affiliations"
                }
            },
            {"$project":{"affiliations.addresses.country_code":1,"affiliations.addresses.country":1,"_id":0}},
            {"$unwind":"$affiliations"}
        ])
        for reg in self.colav_db["authors"].aggregate(pipeline,allowDiskUse=False):
            country=reg["affiliations"]["addresses"][0]["country_code"]
            if not country in country_list:
                country_list.append(country)
                countries.append({"country_code":country,"country":reg["affiliations"]["addresses"][0]["country"]})

        total=cursor.count()
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
        cursor=cursor.skip(max_results*(page-1)).limit(max_results)

        if cursor:
            author_list=[]
            keywords=[]
            for author in cursor:
                entry={
                    "id":author["_id"],
                    "full_name":author["full_name"],
                    "affiliation":[]
                }
                if "affiliations" in author.keys():
                    if len(author["affiliations"])>0:
                        entry["affiliation"]=author["affiliations"][-1]
                        if "id" in entry["affiliation"].keys():
                            affdb=self.colav_db["institutions"].find_one({"_id":entry["affiliation"]["id"]})
                            entry["affiliation"]["logo_url"]=affdb["logo_url"]
                author_list.append(entry)
    
            return {"data":author_list,
                    "filters":{
                        "affiliations":affiliations,
                        "keywords":keywords,
                        "countries":countries
                    },
                    "count":len(author_list),
                    "page":page,
                    "total_results":total
                }
        else:
            return None

    def search_branch(self,branch,keywords="",institution_id=None,max_results=100,page=1):

        if keywords:
            if institution_id:
                cursor=self.colav_db['branches'].find({"$text":{"$search":keywords},"type":branch,"relations.id":ObjectId(institution_id)})
                cursor.sort([("name", ASCENDING)])
   
            else:
                cursor=self.colav_db['branches'].find({"$text":{"$search":keywords},"type":branch})
                cursor.sort([("name", ASCENDING)])
            pipeline=[{"$match":{"$text":{"$search":keywords},"type":branch}}]
            aff_pipeline=[
                {"$match":{"$text":{"$search":keywords},"type":branch}},
                {"$project":{"relations":1}},
                {"$unwind":"$relations"},
                {"$group":{"_id":{"name":"$relations.name","id":"$relations.id"}}}
                

            ] 
        else:
            if institution_id:
                cursor=self.colav_db['branches'].find({"type":branch,"relations.id":ObjectId(institution_id)})
                cursor.sort([("name", ASCENDING)])
            else:
                cursor=self.colav_db['branches'].find({"type":branch})
            pipeline=[]
            aff_pipeline=[
                {"$project":{"relations":1}},
                {"$unwind":"$relations"},
                {"$group":{"_id":{"name":"$relations.name","id":"$relations.id"}}}
            ]

        total=cursor.count()
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
        cursor=cursor.skip(max_results*(page-1)).limit(max_results)

        pipeline.append({"$group":{"_id":{"country_code":"$addresses.country_code","country":"$addresses.country"}}})
        countries=[]
        for res in self.colav_db["branches"].aggregate(pipeline):
            reg=res["_id"]
            if reg["country_code"] and reg["country"]:
                country={"country_code":reg["country_code"][0],"country":reg["country"][0]}
                if not country in countries:
                    countries.append(country)

        affiliations=[reg["_id"] for reg in self.colav_db["branches"].aggregate(aff_pipeline)]
        

        if cursor:
            entity_list=[]
            for entity in cursor:
                entry={
                    "name":entity["name"],
                    "id":str(entity["_id"]),
                    "affiliation":{}
                }
                for relation in entity["relations"]:
                    if relation["type"]=="university":
                        del(relation["type"])
                        del(relation["collection"])
                        entry["affiliation"]=relation

                entity_list.append(entry)
                        
            return {"data":entity_list,
                    "count":len(entity_list),
                    "page":page,
                    "total_results":total
                }
        else:
            return None

    def search_institution(self,keywords="",country="",max_results=100,page=1):
        if keywords:
            if country:
                cursor=self.colav_db['institutions'].find({"$text":{"$search":keywords},"addresses.country_code":country,"external_ids":{"$ne":[]}})
                cursor.sort([("name", ASCENDING)])
            else:
                cursor=self.colav_db['institutions'].find({"$text":{"$search":keywords},"external_ids":{"$ne":[]}})
                cursor.sort([("name", ASCENDING)])
            country_pipeline=[{"$match":{"$text":{"$search":keywords},"external_ids":{"$ne":[]}}}]
        else:
            if country:
                cursor=self.colav_db['institutions'].find({"addresses.country_code":country,"external_ids":{"$ne":[]}})
                cursor.sort([("name", ASCENDING)])
            else:
                cursor=self.colav_db['institutions'].find({"external_ids":{"$ne":[]}})
                cursor.sort([("name", ASCENDING)])
            country_pipeline=[]
            

        country_pipeline.append(
            {
                "$group":{
                    "_id":{"country_code":"$addresses.country_code","country":"$addresses.country"}
                    }
                }
        )
        countries=[]
        for res in self.colav_db["institutions"].aggregate(country_pipeline):
            reg=res["_id"]
            if reg["country_code"] and reg["country"]:
                country={"country_code":reg["country_code"][0],"country":reg["country"][0]}
                if not country in countries:
                    countries.append(country)

        total=cursor.count()
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
        cursor=cursor.skip(max_results*(page-1)).limit(max_results)

        if cursor:
            institution_list=[]
            for institution in cursor:
                entry={
                    "id":institution["_id"],
                    "name":institution["name"],
                    "logo":institution["logo_url"]
                }
                institution_list.append(entry)
    
            return {"data":institution_list,
                    "count":len(institution_list),
                    "page":page,
                    "total_results":total
                }
        else:
            return None

    def search_documents(self,keywords="",tipo=None):
        initial_year=0
        final_year=0    

        if keywords:
            result=self.colav_db['documents'].find({"$text":{"$search":keywords}},{"year_published":1}).sort([("year_published",ASCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    initial_year=result[0]["year_published"]
            result=self.colav_db['documents'].find({"$text":{"$search":keywords}},{"year_published":1}).sort([("year_published",DESCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    final_year=result[0]["year_published"]

            tipos = self.colav_db['documents'].distinct("publication_type.type",{"$text":{"$search":keywords}})

        return{
            "types":tipos,
            "filters":{
                "start_year":initial_year,
                "end_year":final_year
            }

        }
                    
    def search_documents_by_type(self,keywords="",max_results=100,page=1,start_year=None,end_year=None,sort="citations",direction="descending",tipo=None):


        if start_year:
            try:
                start_year=int(start_year)
            except:
                print("Could not convert start year to int")
                return None
        if end_year:
            try:
                end_year=int(end_year)
            except:
                print("Could not convert end year to int")
                return None

        if keywords:
            cursor=self.colav_db['documents'].find({"$text":{"$search":keywords}})
            country_pipeline=[{"$match":{"$text":{"$search":keywords}}}]
            aff_pipeline=[
                {"$match":{"$text":{"$search":keywords}}}
            ]
        else:
            cursor=self.colav_db['documents'].find()
            aff_pipeline=[]

        aff_pipeline.extend([
                {"$unwind":"$affiliations"},{"$project":{"affiliations":1}},
                {"$group":{"_id":"$_id","affiliation":{"$last":"$affiliations"}}},
                {"$group":{"_id":"$affiliation"}}
            ])
        affiliations=[reg["_id"] for reg in self.colav_db["authors"].aggregate(aff_pipeline)]
            



        total=cursor.count()
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
        cursor=cursor.skip(max_results*(page-1)).limit(max_results)

        if sort=="citations" and direction=="ascending":
            cursor.sort([("citations_count",ASCENDING)])
        if sort=="citations" and direction=="descending":
            cursor.sort([("citations_count",DESCENDING)])
        if sort=="year" and direction=="ascending":
            cursor.sort([("year_published",ASCENDING)])
        if sort=="year" and direction=="descending":
            cursor.sort([("year_published",DESCENDING)])

        if cursor:
            paper_list=[]
            for paper in cursor:
                entry={
                    "id":paper["_id"],
                    "title":paper["titles"][0]["title"],
                    "authors":[],
                    "source":"",
                    "open_access_status":paper["open_access_status"],
                    "year_published":paper["year_published"],
                    "citations_count":paper["citations_count"]
                }

                source=self.colav_db["sources"].find_one({"_id":paper["source"]["id"]})
                if source:
                    entry["source"]={"name":source["title"],"id":source["_id"]}
                
                authors=[]
                for author in paper["authors"]:
                    reg_au=self.colav_db["authors"].find_one({"_id":author["id"]})
                    reg_aff=""
                    if author["affiliations"]:
                        reg_aff=self.colav_db["institutions"].find_one({"_id":author["affiliations"][0]["id"]})
                    author_entry={
                        "id":reg_au["_id"],
                        "full_name":reg_au["full_name"],
                        "affiliations":""
                    }
                    if reg_aff:
                        author_entry["affiliations"]={"id":reg_aff["_id"],"name":reg_aff["name"]}
                    authors.append(author_entry)
                entry["authors"]=authors

                paper_list.append(entry)

            return {"data":paper_list,
                    "count":len(paper_list),
                    "page":page,
                    "total_results":total
                }
        else:
            return None
        

    @endpoint('/app/search', methods=['GET'])
    def app_search(self):
        """
        @api {get} /app/search Search
        @apiName app
        @apiGroup CoLav app
        @apiDescription Requests search of different entities in the CoLav database

        @apiParam {String} data Specifies the type of entity (or list of entities) to return, namely paper, institution, faculty, department, author
        @apiParam {String} affiliation The mongo if of the related affiliation of the entity to return
        @apiParam {String} apikey  Credential for authentication

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 204) msg  The HTTP 204 No Content.
        @apiError (Error 200) msg  The HTTP 200 OK.

        @apiSuccessExample {json} Success-Response (data=faculties):
        [
            {
                "name": "Facultad de artes",
                "id": "602c50d1fd74967db0663830",
                "abbreviations": [],
                "external_urls": [
                {
                    "source": "website",
                    "url": "http://www.udea.edu.co/wps/portal/udea/web/inicio/institucional/unidades-academicas/facultades/artes"
                }
                ]
            },
            {
                "name": "Facultad de ciencias agrarias",
                "id": "602c50d1fd74967db0663831",
                "abbreviations": [],
                "external_urls": [
                {
                    "source": "website",
                    "url": "http://www.udea.edu.co/wps/portal/udea/web/inicio/unidades-academicas/ciencias-agrarias"
                }
                ]
            },
            {
                "name": "Facultad de ciencias económicas",
                "id": "602c50d1fd74967db0663832",
                "abbreviations": [
                "FCE"
                ],
                "external_urls": [
                {
                    "source": "website",
                    "url": "http://www.udea.edu.co/wps/portal/udea/web/inicio/institucional/unidades-academicas/facultades/ciencias-economicas"
                }
                ]
            },
            {
                "name": "Facultad de ciencias exactas y naturales",
                "id": "602c50d1fd74967db0663833",
                "abbreviations": [
                "FCEN"
                ],
                "external_urls": [
                {
                    "source": "website",
                    "url": "http://www.udea.edu.co/wps/portal/udea/web/inicio/unidades-academicas/ciencias-exactas-naturales"
                }
                ]
            }
        ]

        @apiSuccessExample {json} Success-Response (data=authors):
            {
                "data": [
                    {
                    "id": "5fc59becb246cc0887190a5c",
                    "full_name": "Johann Hasler Perez",
                    "affiliation": {
                        "id": "60120afa4749273de6161883",
                        "name": "University of Antioquia"
                    },
                    "keywords": [
                        "elliptical orbits",
                        "history of ideas",
                        "history of science",
                        "johannes kepler",
                        "music of the spheres",
                        "planetary music",
                        "speculative music",
                        "alchemical meditation",
                        "atalanta fugiens",
                        "early multimedia",
                        "emblem books",
                        "historical instances of performance",
                        "michael maier"
                    ]
                    },
                    {
                    "id": "5fc59d6bb246cc0887190a5d",
                    "full_name": "Carolina Santamaria Delgado",
                    "affiliation": {
                        "id": "60120afa4749273de6161883",
                        "name": "University of Antioquia"
                    },
                    "keywords": [
                        "art in the university",
                        "artist-professor",
                        "intellectual production",
                        "music as an academic field",
                        "research-creation",
                        "the world of art"
                    ]
                    }
                ],
                "filters": {
                    "affiliations": [
                    {
                        "id": "60120afa4749273de6161883",
                        "name": "University of Antioquia"
                    }
                    ],
                    "keywords": [],
                    "countries": [
                    "CO"
                    ]
                },
                "count": 2,
                "page": 2,
                "total_results": 565
            }
        """
        data = self.request.args.get('data')
        tipo = self.request.args.get('type')

        if data=="faculties":
            max_results=self.request.args.get('max') if 'max' in self.request.args else 100
            page=self.request.args.get('page') if 'page' in self.request.args else 1
            keywords = self.request.args.get('keywords') if "keywords" in self.request.args else ""
            result=self.search_branch("faculty",keywords=keywords,max_results=max_results,page=page)
        elif data=="departments":
            max_results=self.request.args.get('max') if 'max' in self.request.args else 100
            page=self.request.args.get('page') if 'page' in self.request.args else 1
            keywords = self.request.args.get('keywords') if "keywords" in self.request.args else ""
            result=self.search_branch("department",keywords=keywords,max_results=max_results,page=page)
        elif data=="groups":
            max_results=self.request.args.get('max') if 'max' in self.request.args else 100
            page=self.request.args.get('page') if 'page' in self.request.args else 1
            keywords = self.request.args.get('keywords') if "keywords" in self.request.args else ""
            id = self.request.args.get('institution') if "institution" in self.request.args else ""
            result=self.search_branch("group",keywords=keywords,institution_id=id,max_results=max_results,page=page)
        elif data=="authors":
            max_results=self.request.args.get('max') if 'max' in self.request.args else 100
            page=self.request.args.get('page') if 'page' in self.request.args else 1
            keywords = self.request.args.get('keywords') if "keywords" in self.request.args else ""
            result=self.search_author(keywords=keywords,max_results=max_results,page=page)
        elif data=="institutions":
            max_results=self.request.args.get('max') if 'max' in self.request.args else 100
            page=self.request.args.get('page') if 'page' in self.request.args else 1
            keywords = self.request.args.get('keywords') if "keywords" in self.request.args else ""
            country = self.request.args.get('country') if "country" in self.request.args else ""
            result=self.search_institution(keywords=keywords,country=country,max_results=max_results,page=page)
        elif data=="literature":
            max_results=self.request.args.get('max') if 'max' in self.request.args else 100
            page=self.request.args.get('page') if 'page' in self.request.args else 1
            keywords = self.request.args.get('keywords') if "keywords" in self.request.args else ""
            country = self.request.args.get('country') if "country" in self.request.args else ""
            start_year=self.request.args.get('start_year')
            end_year=self.request.args.get('end_year')
            sort=self.request.args.get('sort')
            if tipo == None:
                result=self.search_documents(keywords=keywords)
            else:
                result=self.search_documents_by_type(keywords=keywords,max_results=max_results,
                    page=page,start_year=start_year,end_year=end_year,sort=sort,direction="descending",tipo=tipo)

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