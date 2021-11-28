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
            group_name = ""
            group_id = ""
            for author in cursor:
                entry={
                    "id":author["_id"],
                    "name":author["full_name"],
                    "affiliation":{"institution":{"name":"","id":""},"group":{"name":"","id":""}}
                }
                if "affiliations" in author.keys():
                    if len(author["affiliations"])>0:
                        entry["affiliation"]["institution"]["name"]=author["affiliations"][-1]["name"]
                        entry["affiliation"]["institution"]["id"]  =author["affiliations"][-1]["id"]
                
                if "branches" in author.keys():
                    for i in range(len(author["branches"])):    
                        if author["branches"][i]["type"]=="group":
                            group_name = author["branches"][i]["name"]
                            group_id =   author["branches"][i]["id"]

                
                
                entry["affiliation"]["group"]["name"]=group_name
                entry["affiliation"]["group"]["id"]  =group_id
                
                


                author_list.append(entry)
    
            return {
                    "total_results":total,
                    "count":len(author_list),
                    "page":page,
                    "data":author_list
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

    def search_info(self,keywords=""):

        initial_year=0
        final_year = 0

        if keywords: 
            result=self.colav_db['documents'].find({"$text":{"$search":keywords}},{"year_published":1}).sort([("year_published",ASCENDING)]).limit(1)
            if result:
                result=list(result)
                print(result)
                if len(result)>0:
                    initial_year=result[0]["year_published"]
            result=self.colav_db['documents'].find({"$text":{"$search":keywords}},{"year_published":1}).sort([("year_published",DESCENDING)]).limit(1)
            if result:
                result=list(result)
                print(result)
                if len(result)>0:
                    final_year=result[0]["year_published"]
                

            filters={
                "start_year":initial_year,
                "end_year":final_year
            }

            print("initial_year",initial_year)
            print("final_year",final_year)

            return {"filters": filters}
        else:
            return None

    def search_documents(self,keywords="",start_year=None,end_year=None):
        open_access=[]

       
        
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

            if start_year and not end_year:
                venn_query={"year_published":{"$gte":start_year},"$text":{"$search":keywords}}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year},"$text":{"$search":keywords}})  },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year},"$text":{"$search":keywords}})   },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year},"$text":{"$search":keywords}}) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year},"$text":{"$search":keywords}}) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year},"$text":{"$search":keywords}}) }
                ])
            elif end_year and not start_year:
                venn_query={"year_published":{"$lte":end_year},"$text":{"$search":keywords}}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$lte":end_year},"$text":{"$search":keywords}})  },
                    {"type":"gold"  ,"value": self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$lte":end_year},"$text":{"$search":keywords}})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$lte":end_year},"$text":{"$search":keywords}}) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$lte":end_year},"$text":{"$search":keywords}}) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$lte":end_year},"$text":{"$search":keywords}}) }
                ])
            elif start_year and end_year:
                venn_query={"year_published":{"$gte":start_year,"$lte":end_year},"$text":{"$search":keywords}}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year,"$lte":end_year},"$text":{"$search":keywords} }) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year,"$lte":end_year},"$text":{"$search":keywords}})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year,"$lte":end_year},"$text":{"$search":keywords}})},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year,"$lte":end_year},"$text":{"$search":keywords}})},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year,"$lte":end_year},"$text":{"$search":keywords}})}
                ])
            else:
                venn_query={"$text":{"$search":keywords}}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","$text":{"$search":keywords}}) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","$text":{"$search":keywords}})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","$text":{"$search":keywords}})},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","$text":{"$search":keywords}})},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","$text":{"$search":keywords}})}
                ])


            tipos = self.colav_db['documents'].distinct("publication_type.type",{"$text":{"$search":keywords}})

        else:
            if start_year and not end_year:
                venn_query={"year_published":{"$gte":start_year}}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year} })  },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year} })   },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year} }) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year} }) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year} }) }
                ])
            elif end_year and not start_year:
                venn_query={"year_published":{"$lte":end_year} }
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$lte":end_year} })  },
                    {"type":"gold"  ,"value": self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$lte":end_year} })  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$lte":end_year} }) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$lte":end_year} }) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$lte":end_year} }) }
                ])
            elif start_year and end_year:
                venn_query={"year_published":{"$gte":start_year,"$lte":end_year} }
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year,"$lte":end_year} }) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year,"$lte":end_year} })  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year,"$lte":end_year} })},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year,"$lte":end_year} })},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year,"$lte":end_year} })}
                ])
            else:
                venn_query={}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green" }) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold" })  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze" })},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed" })},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid" })}
                ])


            tipos = self.colav_db['documents'].distinct("publication_type.type")

        return {
            "open_access":open_access,
            "venn_source":self.get_venn(venn_query),
            "types":tipos
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
            cursor=self.colav_db['documents'].find({"$text":{"$search":keywords},"publication_type.type":tipo})
            aff_pipeline=[
                {"$match":{"$text":{"$search":keywords},"publication_type.type":tipo}}
            ]
        else:
            cursor=self.colav_db['documents'].find({"publication_type.type":tipo})
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
                        "affiliation": { "group":{ "name":"", "id":""  } }
                    }
                    if reg_aff:
                        author_entry["affiliation"]["group"]["name"] = reg_aff["name"]
                        author_entry["affiliation"]["group"]["id"]   = reg_aff["_id"]
                  

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


    def get_venn(self,venn_query):
        venn_source={
            "scholar":0,"lens":0,"wos":0,"scopus":0,
            "scholar_lens":0,"scholar_wos":0,"scholar_scopus":0,"lens_wos":0,"lens_scopus":0,"wos_scopus":0,
            "scholar_lens_wos":0,"scholar_wos_scopus":0,"scholar_lens_scopus":0,"lens_wos_scopus":0,
            "scholar_lens_wos_scopus":0
        }
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["scholar"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":"lens"},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["lens"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":"wos"},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["wos"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":"scopus"}]
        venn_source["scopus"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":"lens"},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["scholar_lens"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":"wos"},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["scholar_wos"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":"scopus"}]
        venn_source["scholar_scopus"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":"lens"},
                {"source_checked.source":"wos"},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["lens_wos"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":"lens"},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":"scopus"}]
        venn_source["lens_scopus"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":"wos"},
                {"source_checked.source":"scopus"}]
        venn_source["wos_scopus"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":"lens"},
                {"source_checked.source":"wos"},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["scholar_lens_wos"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":"wos"},
                {"source_checked.source":"scopus"}]
        venn_source["scholar_wos_scopus"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":"lens"},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":"scopus"}]
        venn_source["scholar_lens_scopus"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":"lens"},
                {"source_checked.source":"wos"},
                {"source_checked.source":"scopus"}]
        venn_source["lens_wos_scopus"]=self.colav_db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":"lens"},
                {"source_checked.source":"wos"},
                {"source_checked.source":"scopus"}]
        venn_source["scholar_lens_wos_scopus"]=self.colav_db['documents'].count_documents(venn_query)

        return venn_source        

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

        if data=="info":
            keywords = self.request.args.get('keywords') if "keywords" in self.request.args else ""
            result = self.search_info(keywords=keywords)


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
                result=self.search_documents(keywords=keywords,start_year=start_year,end_year=end_year)
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