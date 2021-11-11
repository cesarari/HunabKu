from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from bson import ObjectId
from pymongo import ASCENDING,DESCENDING
from pickle import load
from datetime import date
from math import log
from flask import redirect


class InstitutionsApp(HunabkuPluginBase):
    def __init__(self, hunabku):
        super().__init__(hunabku)

    def get_info(self,idx):
        institution = self.colav_db['institutions'].find_one({"_id":ObjectId(idx)})
        if institution:
            entry={"id":institution["_id"],
                "name":institution["name"],
                "external_urls":institution["external_urls"],
                "logo":institution["logo_url"]
            }

        if(idx):
            result=self.colav_db['documents'].find({"authors.affiliations.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",ASCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    initial_year=result[0]["year_published"]
            result=self.colav_db['documents'].find({"authors.affiliations.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",DESCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    final_year=result[0]["year_published"]

            filters={
                "start_year":initial_year,
                "end_year":final_year
             }
            
            return {"data": entry, "filters": filters }
        else:
            return None
    
    def hindex(self,citation_list):
        return sum(x >= i + 1 for i, x in enumerate(sorted(list(citation_list), reverse=True)))


    def get_citations(self,idx=None,start_year=None,end_year=None):

 
        entry={
            "citations":0,
            "yearly_citations":[],
            "geo": []
        }

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
        


        pipeline=[
            {"$match":{"authors.affiliations.id":ObjectId(idx)}}
        ]


        pipeline.extend([
            {"$match":{"citations":{"$ne":[]}}},
            {"$unwind":"$citations"},
            {"$lookup":{
                "from":"documents",
                "localField":"citations",
                "foreignField":"_id",
                "as":"citers"}
            },
            {"$unwind":"$citers"}])


        if start_year and not end_year:
            pipeline.extend([{"$match":{"citers.year_published":{"$gte":start_year}}}])
        elif end_year and not start_year:
            pipeline.extend([{"$match":{"citers.year_published":{"$lte":end_year}}}])
        elif start_year and end_year:
            pipeline.extend([{"$match":{"citers.year_published":{"$gte":start_year,"$lte":end_year}}}])

            


        geo_pipeline = pipeline[:] # a clone


        pipeline.extend([
            {"$group":{
                "_id":"$citers.year_published","count":{"$sum":1}}
            },
            {"$sort":{
                "_id":-1
            }}
        ])



 


    

        geo_pipeline.extend([
            {"$unwind":"$citers.authors"},
            {"$project":{"citers.authors.affiliations":1}},
            {"$lookup":{"from":"institutions","foreignField":"_id","localField":"citers.authors.affiliations.id","as":"affiliation"}},
            {"$project":{"affiliation.addresses.country":1,"affiliation.addresses.country_code":1}},
            {"$unwind":"$affiliation"},{"$group":{"_id":"$affiliation.addresses.country_code","count":{"$sum":1},
             "country": {"$first": "$affiliation.addresses.country"}}},{"$project": {"country": 1,"_id":1,"count": 1, "log_count": {"$ln": "$count"}}},
            {"$unwind": "$_id"}, {"$unwind": "$country"}
        ])


        for idx,reg in enumerate(self.colav_db["documents"].aggregate(pipeline)):
            entry["citations"]+=reg["count"]
            entry["yearly_citations"].append({"year":reg["_id"],"value":reg["count"]})




        for i, reg in enumerate(self.colav_db["documents"].aggregate(geo_pipeline)):
            entry["geo"].append({"country": reg["country"],
                                 "country_code": reg["_id"],
                                 "count": reg["count"],
                                 "log_count": reg["log_count"]}
                                 )
    
        return {"data": entry}

    
    def get_authors(self,idx=None):
        if idx:

            pipeline=[
                {"$match":{"authors.affiliations.id":ObjectId(idx)}}
            ]

            pipeline.extend([

                {"$unwind":"$authors"},
                {"$match":{"authors.affiliations.id":ObjectId(idx)}},
                {"$group":{"_id":"$authors.id","papers_count":{"$sum":1},"citations_count":{"$sum":"$citations_count"},"author":{"$first":"$authors"}}},
                {"$sort":{"citations_count":-1}},
                {"$project":{"_id":1,"author.full_name":1,"author.affiliations.name":1,"papers_count":1,"citations_count":1}},



            ])

            result= self.colav_db["documents"].aggregate(pipeline)
        
            entry = []

            for reg in result:
                entry.append({
                    "id":reg["_id"],
                    "name":reg["author"]["full_name"],
                    "papers_count":reg["papers_count"],
                    "citations_count":reg["citations_count"],
                    "affiliation":reg["author"]["affiliations"][0]["name"]
                })
            
        return {"data":entry}


    def get_coauthors(self,idx=None):
        if idx:
            pipeline = [ 
                {"$match":{"authors.affiliations.id":ObjectId(idx)} },
                {"$unwind":"$authors"},{"$match":{"authors.affiliations.id": {"$ne": ObjectId(idx)}}},
                {"$project":{"authors.affiliations.id":1,"authors.affiliations.name":1}},
                {"$lookup":{"from":"institutions","localField":"authors.affiliations.id","foreignField":"_id","as":"coInstitutions"}},
                {"$project":{"coInstitutions._id":1,"coInstitutions.name":1,"coInstitutions.addresses.country":1,"coInstitutions.addresses.country_code":1}},
                {"$sort":{"coInstitutions.addresses.country":1}}
            ]

            result= self.colav_db["documents"].aggregate(pipeline)

            entry = []

            for reg in result:
                try:
                    entry.append({
                        "_id":reg["coInstitutions"][0]["_id"],
                        "name":reg["coInstitutions"][0]["name"],
                        "country":reg["coInstitutions"][0]["addresses"][0]["country"],
                        "country_code":reg["coInstitutions"][0]["addresses"][0]["country_code"]
                    })
                except:
                    continue

        return {"data":entry}

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


    def get_production_by_type(self,idx=None,max_results=100,page=1,start_year=None,end_year=None,sort="descending",direction=None,tipo=None):

        total = 0

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

        if idx:

            if start_year and not end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.affiliations.id":ObjectId(idx)})

            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})

            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})

            else:
                cursor=self.colav_db['documents'].find({"authors.affiliations.id":ObjectId(idx),"publication_type.type":tipo})


        
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
 

        if sort=="citations" and direction=="ascending":
            cursor.sort([("citations_count",ASCENDING)])
        if sort=="citations" and direction=="descending":
            cursor.sort([("citations_count",DESCENDING)])
        if sort=="year" and direction=="ascending":
            cursor.sort([("year_published",ASCENDING)])
        if sort=="year" and direction=="descending":
            cursor.sort([("year_published",DESCENDING)])

        cursor=cursor.skip(max_results*(page-1)).limit(max_results)

        entry=[]

        for doc in cursor:
            
            authors=[]
            for author in doc["authors"]:
                au_entry={}
                author_db=self.colav_db["authors"].find_one({"_id":author["id"]})
                if author_db:
                    au_entry={"full_name":author_db["full_name"],"id":author_db["_id"]}
                affiliations=[]
                for aff in author["affiliations"]:
                    aff_entry={}
                    aff_db=self.colav_db["institutions"].find_one({"_id":aff["id"]})
                    if aff_db:
                        aff_entry={"name":aff_db["name"],"id":aff_db["_id"]}
                    
                    affiliations.append(aff_entry)
                au_entry["affiliations"]=affiliations
                authors.append(au_entry)



            try:
                if doc["publication_type"]["source"]=="lens":

                    source=self.colav_db["sources"].find_one({"_id":doc["source"]["id"]})

                    entry.append({
                    "id":doc["_id"],
                    "title":doc["titles"][0]["title"],
                    "citations_count":doc["citations_count"],
                    "year_published":doc["year_published"],
                    "open_access_status":doc["open_access_status"],
                    "source":{"name":source["title"],"id":str(source["_id"])},
                    "authors":authors
                    })

            except:
                continue
        return {"total":total,"data":entry,"page":page}

    def get_production(self,idx=None,start_year=None,end_year=None,sort=None,direction=None):
        
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
        if idx:

            if start_year and not end_year:
                venn_query={"year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{ "$gte":start_year},"authors.affiliations.id":ObjectId(idx)})  },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":  {"$gte":start_year},"authors.affiliations.id":ObjectId(idx)})   },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year},"authors.affiliations.id":ObjectId(idx)}) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year},"authors.affiliations.id":ObjectId(idx)}) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year},"authors.affiliations.id":ObjectId(idx)}) }
                ])
            elif end_year and not start_year:
                venn_query={"year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published": {"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})  },
                    {"type":"gold"  ,"value": self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published": {"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$lte":end_year},"authors.affiliations.id":ObjectId(idx)}) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$lte":end_year},"authors.affiliations.id":ObjectId(idx)}) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$lte":end_year},"authors.affiliations.id":ObjectId(idx)}) }
                ])
            elif start_year and end_year:
                venn_query={"year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published": {"$gte":start_year,"$lte":end_year},"authors.affiliations.id":ObjectId(idx)}) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":  {"$gte":start_year,"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})}
                ])
            else:
                venn_query={"authors.affiliations.branches.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green" ,"authors.affiliations.id":ObjectId(idx)}) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold"  ,"authors.affiliations.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","authors.affiliations.id":ObjectId(idx)})},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","authors.affiliations.id":ObjectId(idx)})},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","authors.affiliations.id":ObjectId(idx)})}
                ])


 



        tipos = self.colav_db['documents'].distinct("publication_type.type",{"authors.affiliations.id":ObjectId(idx)})


        return {
            "open_access":open_access,
            "venn_source":self.get_venn(venn_query),
            "types":tipos

            }


    def get_csv(self,idx=None,start_year=None,end_year=None,sort=None,direction=None):
        papers=[]

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
        if idx:
            if start_year and not end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.affiliations.id":ObjectId(idx)})
            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})
            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})
            else:
                cursor=self.colav_db['documents'].find({"authors.affiliations.id":ObjectId(idx)})
        else:
            cursor=self.colav_db['documents'].find()

        if sort=="citations" and direction=="ascending":
            cursor.sort({"citations_count":pymongo.ASCENDING})
        if sort=="citations" and direction=="descending":
            cursor.sort({"citations_count":pymongo.DESCENDING})
        if sort=="year" and direction=="ascending":
            cursor.sort({"year_published":pymongo.ASCENDING})
        if sort=="year" and direction=="descending":
            cursor.sort({"year_published":pymongo.DESCENDING})

        csv_text="id\tpublication_type\ttitle\tabstract\tvolume\tissue\tstart_page\tend_page\tyear_published\tdate_published\t"
        csv_text+="funding_organization\tis_open_access\topen_access_status\tdoi\tjournal_name\tpublisher\tissn\t"
        csv_text+="author_id\tauthor_name\taffiliation_id\taffiliation_name\taffiliation_country\n"

        for paper in cursor:
            csv_text+=str(paper["_id"])
            csv_text+="\t"+paper["publication_type"]
            csv_text+="\t"+paper["titles"][0]["title"].replace("\t","").replace("\n","").replace("\r","")
            csv_text+="\t"+paper["abstract"].replace("\t","").replace("\n","").replace("\r","")
            csv_text+="\t"+str(paper["volume"])
            csv_text+="\t"+str(paper["issue"])
            csv_text+="\t"+str(paper["start_page"])
            csv_text+="\t"+str(paper["end_page"])
            csv_text+="\t"+str(paper["year_published"])
            try:
                ts=int(paper["date_published"])
                csv_text+="\t"+date.fromtimestamp(ts).strftime("%d-%m-%Y")
            except:
                csv_text+="\t"+""
            csv_text+="\t"+paper["funding_organization"].replace("\t","").replace("\n","").replace("\r","")
            csv_text+="\t"+str(paper["is_open_access"])
            csv_text+="\t"+paper["open_access_status"]
            doi_entry=""
            for ext in paper["external_ids"]:
                if ext["source"]=="doi":
                    doi_entry=ext["id"]
            csv_text+="\t"+str(doi_entry)

            source=self.colav_db["sources"].find_one({"_id":paper["source"]["id"]})
            if source:
                csv_text+="\t"+source["title"].replace("\t","").replace("\n","").replace("\r","")
                csv_text+="\t"+source["publisher"]
                serial_entry=""
                for serial in source["serials"]:
                    if serial["type"]=="issn" or serial["type"]=="eissn" or serial["type"]=="pissn":
                        serial_entry=serial["value"]
                csv_text+="\t"+serial_entry

            csv_text+="\t"+str(paper["authors"][0]["id"])
            author_db=self.colav_db["authors"].find_one({"_id":paper["authors"][0]["id"]})
            if author_db:
                csv_text+="\t"+author_db["full_name"]
            else:
                csv_text+="\t"+""
            aff_db=""
            if "affiliations" in paper["authors"][0].keys():
                if len(paper["authors"][0]["affiliations"])>0:
                    csv_text+="\t"+str(paper["authors"][0]["affiliations"][0]["id"])
                    aff_db=self.colav_db["institutions"].find_one({"_id":paper["authors"][0]["affiliations"][0]["id"]})
            if aff_db:
                csv_text+="\t"+aff_db["name"]
                country_entry=""
                if "addresses" in aff_db.keys():
                    if len(aff_db["addresses"])>0:
                        country_entry=aff_db["addresses"][0]["country"]
                csv_text+="\t"+country_entry
            else:
                csv_text+="\t"+""
                csv_text+="\t"+""
                csv_text+="\t"+""
            csv_text+="\n"
        return csv_text
    
    def get_json(self,idx=None,start_year=None,end_year=None,sort=None,direction=None):
        papers=[]

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
        if idx:
            if start_year and not end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.affiliations.id":ObjectId(idx)})
            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})
            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.id":ObjectId(idx)})
            else:
                cursor=self.colav_db['documents'].find({"authors.affiliations.id":ObjectId(idx)})
        else:
            cursor=self.colav_db['documents'].find()



        if sort=="citations" and direction=="ascending":
            cursor.sort({"citations_count":pymongo.ASCENDING})
        if sort=="citations" and direction=="descending":
            cursor.sort({"citations_count":pymongo.DESCENDING})
        if sort=="year" and direction=="ascending":
            cursor.sort({"year_published":pymongo.ASCENDING})
        if sort=="year" and direction=="descending":
            cursor.sort({"year_published":pymongo.DESCENDING})

        for paper in cursor:
            entry=paper
            source=self.colav_db["sources"].find_one({"_id":paper["source"]["id"]})
            if source:
                entry["source"]=source
            authors=[]
            for author in paper["authors"]:
                au_entry=author
                author_db=self.colav_db["authors"].find_one({"_id":author["id"]})
                if author_db:
                    au_entry=author_db
                affiliations=[]
                for aff in author["affiliations"]:
                    aff_entry=aff
                    aff_db=self.colav_db["institutions"].find_one({"_id":aff["id"]})
                    if aff_db:
                        aff_entry=aff_db
                    branches=[]
                    if "branches" in aff.keys():
                        for branch in aff["branches"]:
                            branch_db=self.colav_db["branches"].find_one({"_id":branch["id"]}) if "id" in branch.keys() else ""
                            if branch_db:
                                branches.append(branch_db)
                    aff_entry["branches"]=branches
                    affiliations.append(aff_entry)
                au_entry["affiliations"]=affiliations
                authors.append(au_entry)
            entry["authors"]=authors
            papers.append(entry)
        return str(papers)
    
 
    @endpoint('/app/institutions', methods=['GET'])
    def app_institutions(self):
        """
        @api {get} /app/institutions Institutions
        @apiName app
        @apiGroup CoLav app
        @apiDescription Responds with information about the institutions

        @apiParam {String} apikey Credential for authentication
        @apiParam {String} data (info,production) Whether is the general information or the production
        @apiParam {Object} id The mongodb id of the institution requested
        @apiParam {Int} start_year Retrieves result starting on this year
        @apiParam {Int} end_year Retrieves results up to this year
        @apiParam {Int} max Maximum results per page
        @apiParam {Int} page Number of the page
        @apiParam {String} sort (citations,year) Sorts the results by key in descending order

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 204) msg  The HTTP 204 No Content.
        @apiError (Error 200) msg  The HTTP 200 OK.

        @apiSuccessExample {json} Success-Response (data=info):
        {
            "id": "60120afa4749273de6161883",
            "name": "University of Antioquia",
            "external_urls": [
                {
                "source": "wikipedia",
                "url": "http://en.wikipedia.org/wiki/University_of_Antioquia"
                },
                {
                "source": "site",
                "url": "http://www.udea.edu.co/portal/page/portal/EnglishPortal/EnglishPortal"
                }
            ],
            "departments": [
                {
                "name": "Departamento de artes visuales",
                "id": "602c50f9fd74967db0663854"
                },
                {
                "name": "Departamento de música",
                "id": "602c50f9fd74967db0663855"
                },
                {
                "name": "Departamento de teatro",
                "id": "602c50f9fd74967db0663856"
                },
                {
                "name": "Decanatura facultad de artes",
                "id": "602c50f9fd74967db0663857"
                },
                {
                "name": "Instituto de matemáticas",
                "id": "602c50f9fd74967db0663858"
                },
                {
                "name": "Instituto de física",
                "id": "602c50f9fd74967db0663859"
                },
                {
                "name": "Instituto de biología",
                "id": "602c50f9fd74967db066385a"
                },
                {
                "name": "Instituto de química",
                "id": "602c50f9fd74967db066385b"
                },
                {
                "name": "Departamento de bioquímica",
                "id": "602c50f9fd74967db0663891"
                },
                {
                "name": "Departamento de farmacología y toxicología",
                "id": "602c50f9fd74967db0663892"
                },
                {
                "name": "Departamento de patología",
                "id": "602c50f9fd74967db0663893"
                },
                {
                "name": "Departamento de microbiología y parasitología",
                "id": "602c50f9fd74967db0663894"
                },
                {
                "name": "Departamento de medicina interna",
                "id": "602c50f9fd74967db0663895"
                },
                {
                "name": "Departamento de cirugía",
                "id": "602c50f9fd74967db0663896"
                }
            ],
            "faculties": [
                {
                "name": "Facultad de artes",
                "id": "602c50d1fd74967db0663830"
                },
                {
                "name": "Facultad de ciencias agrarias",
                "id": "602c50d1fd74967db0663831"
                },
                {
                "name": "Facultad de ciencias económicas",
                "id": "602c50d1fd74967db0663832"
                },
                {
                "name": "Facultad de ciencias exactas y naturales",
                "id": "602c50d1fd74967db0663833"
                },
                {
                "name": "Facultad de ciencias farmacéuticas y alimentarias",
                "id": "602c50d1fd74967db0663834"
                },
                {
                "name": "Facultad de ciencias sociales y humanas",
                "id": "602c50d1fd74967db0663835"
                },
                {
                "name": "Facultad de comunicaciones y filología",
                "id": "602c50d1fd74967db0663836"
                },
                {
                "name": "Facultad de derecho y ciencias políticas",
                "id": "602c50d1fd74967db0663837"
                },
                {
                "name": "Facultad de educación",
                "id": "602c50d1fd74967db0663838"
                },
                {
                "name": "Facultad de enfermería",
                "id": "602c50d1fd74967db0663839"
                },
                {
                "name": "Facultad de ingeniería",
                "id": "602c50d1fd74967db066383a"
                },
                {
                "name": "Facultad de medicina",
                "id": "602c50d1fd74967db066383b"
                },
                {
                "name": "Facultad de odontología",
                "id": "602c50d1fd74967db066383c"
                },
                {
                "name": "Facultad de salud pública",
                "id": "602c50d1fd74967db066383d"
                },
                {
                "name": "Escuela de idiomas",
                "id": "602c50d1fd74967db066383e"
                },
                {
                "name": "Escuela interamericana de bibliotecología",
                "id": "602c50d1fd74967db066383f"
                },
                {
                "name": "Escuela de microbiología",
                "id": "602c50d1fd74967db0663840"
                },
                {
                "name": "Escuela de nutrición y dietética",
                "id": "602c50d1fd74967db0663841"
                },
                {
                "name": "Instituto de filosofía",
                "id": "602c50d1fd74967db0663842"
                },
                {
                "name": "Instituto universitario de educación física y deporte",
                "id": "602c50d1fd74967db0663843"
                },
                {
                "name": "Instituto de estudios políticos",
                "id": "602c50d1fd74967db0663844"
                },
                {
                "name": "Instituto de estudios regionales",
                "id": "602c50d1fd74967db0663845"
                },
                {
                "name": "Corporación académica ambiental",
                "id": "602c50d1fd74967db0663846"
                },
                {
                "name": "Corporación académica ciencias básicas biomédicas",
                "id": "602c50d1fd74967db0663847"
                },
                {
                "name": "Corporación académica para el estudio de patologías tropicales",
                "id": "602c50d1fd74967db0663848"
                }
            ],
            "area_groups": [],
            "logo": ""
        }
        @apiSuccessExample {json} Success-Response (data=production):
            {
                "data": [
                    {
                    "_id": "602ef788728ecc2d8e62d4f1",
                    "title": "Product and quotient of correlated beta variables",
                    "source": {
                        "name": "Applied Mathematics Letters",
                        "_id": "602ef788728ecc2d8e62d4ef"
                    },
                    "authors": [
                        {
                        "full_name": "Daya Krishna Nagar",
                        "_id": "5fc5b0a5b246cc0887190a69",
                        "affiliations": [
                            {
                            "name": "University of Antioquia",
                            "_id": "60120afa4749273de6161883",
                            "branches": [
                                {
                                "name": "Facultad de ciencias exactas y naturales",
                                "type": "faculty",
                                "_id": "602c50d1fd74967db0663833"
                                },
                                {
                                "name": "Instituto de matemáticas",
                                "type": "department",
                                "_id": "602c50f9fd74967db0663858"
                                },
                                {
                                "name": "Análisis multivariado",
                                "type": "group",
                                "_id": "602c510ffd74967db06638d6"
                                }
                            ]
                            }
                        ]
                        },
                        {
                        "full_name": "Johanna Marcela Orozco Castañeda",
                        "_id": "5fc5bebab246cc0887190a70",
                        "affiliations": [
                            {uest.args.get('start_year')
            end_year=self.request.args.get('end_year')
            coauthors=self.get_
                            "name": "University of Antioquia",
                            "_id": "60120afa4749273de6161883",
                            "branches": [
                                {
                                "name": "Facultad de ciencias exactas y naturales",
                                "type": "faculty",
                                "_id": "602c50d1fd74967db0663833"
                                },
                                {
                                "name": "Instituto de matemáticas",
                                "type": "department",
                                "_id": "602c50f9fd74967db0663858"
                                }
                            ]
                            }
                        ]
                        },
                        {
                        "full_name": "Daya Krishna Nagar",
                        "_id": "5fc5b0a5b246cc0887190a69",
                        "affiliations": [
                            {
                            "name": "Bowling Green State University",
                            "_id": "60120add4749273de616099f",
                            "branches": []
                            },
                            {
                            "name": "Univ Antioquia",
                            "_id": "602ef788728ecc2d8e62d4f0",
                            "branches": []
                            }
                        ]
                        }
                    ]
                    }
                ],
                "count": 73,
                "page": 1,
                "total_results": 73,
                "initial_year": 1995,
                "final_year": 2017,
                "open_access": {
                    "green": 9,
                    "gold": 17,
                    "bronze": 6,
                    "closed": 39,
                    "hybrid": 2
                },
                "venn_source": {
                    "scholar": 0,
                    "lens": 0,
                    "oadoi": 0,
                    "wos": 0,
                    "scopus": 0,
                    "lens_wos_scholar_scopus": 55,
                    "lens_scholar": 6,
                    "lens_scholar_scopus": 6,
                    "lens_wos_scholar": 6
                }
            }
        @apiSuccessExample {json} Success-Response (data=citations):
            HTTP/1.1 200 OK
            {
                "data": {
                    "citations": 1815,
                    "H5": 8,
                    "yearly_citations": {
                    "2008": 10,
                    "2009": 137,
                    "2010": 240,
                    "2011": 11,
                    "2012": 46,
                    "2013": 67,
                    "2014": 88,
                    "2015": 166,
                    "2016": 66,
                    "2017": 87,
                    "2018": 35,
                    "2019": 4,
                    "2020": 4
                    },
                    "network": {}
                },
                "filters": {
                    "initial_year": 1995,
                    "final_year": 2020
                }
            }
        @apiSuccessExample {json} Success-Response (data=apc):
        HTTP/1.1 200 OK
        {
            "data": {
                "yearly": {
                "2006": 25333.215809352663,
                "2007": 31212.916051395667,
                "2008": 55634.25857670785,
                "2009": 54698.475858931975,
                "2010": 47683.47371715034,
                "2011": 84837.57770613344,
                "2012": 87631.29377989819,
                "2013": 106924.28252286707,
                "2014": 171037.16532375227,
                "2015": 159642.93025535543,
                "2016": 220892.6144583558,
                "2017": 246995.35012787356,
                "2018": 301777.0124037427,
                "2019": 346262.03413552087,
                "2020": 154102.28675748224
                },
                "faculty": {
                "602c50d1fd74967db066383b": {
                    "name": "Facultad de Medicina",
                    "value": 688505.4513403034
                },
                "602c50d1fd74967db066383a": {
                    "name": "Facultad de Ingeniería",
                    "value": 175085.68733245516
                },
                "602c50d1fd74967db0663833": {
                    "name": "Facultad de Ciencias Exactas y Naturales",
                    "value": 380902.37390428863
                },
                "602c50d1fd74967db0663831": {
                    "name": "Facultad de Ciencias Agrarias",
                    "value": 89374.5371867811
                },
                "602c50d1fd74967db0663835": {
                    "name": "Facultad de Ciencias Sociales y Humanas",
                    "value": 2237.28
                }
                },
                "department": {
                "602c50f9fd74967db0663895": {
                    "name": "Departamento de Medicina Interna",
                    "value": 69074.85558893369
                },
                "602c50f9fd74967db0663883": {
                    "name": "Departamento de Ingeniería Industrial",
                    "value": 2317.4396001110804
                },
                "602c50f9fd74967db066385a": {
                    "name": "Instituto de Biología",
                    "value": 182704.58261736613
                },
                "602c50f9fd74967db0663893": {
                    "name": "Departamento de Patología",
                    "value": 3711.3056
                },
                "602c50f9fd74967db066389c": {
                    "name": "Departamento de Medicina Física y Rehabilitación",
                    "value": 1890.3011862842297
                },
                "602c50f9fd74967db066385f": {
                    "name": "Departamento de Antropología",
                    "value": 300
                }
                },
                "group": {
                "602c510ffd74967db0663947": {
                    "name": "Grupo Académico de Epidemiología Clínica",
                    "value": 23510.433610132986
                },
                "602c510ffd74967db06638d9": {
                    "name": "Centro de Investigaciones Básicas y Aplicadas en Veterinaria",
                    "value": 12869.809579159686
                },
                "602c510ffd74967db06639d0": {
                    "name": "Grupo de Química-Física Teórica",
                    "value": 6156.785263507203
                },
                "609cbe1f2ecb2ac1eee78eb1": {
                    "name": "Grupo de Entomología Médica",
                    "value": 13696.310458738084
                },
                "602c510ffd74967db066390a": {
                    "name": "Inmunomodulación",
                    "value": 6536.5592890863645
                },
                "602c510ffd74967db0663919": {
                    "name": "Grupo de Investigación en Psicologia Cognitiva",
                    "value": 1937.2800000000002
                },
                "602c510ffd74967db06639dd": {
                    "name": "Ecología Lótica: Islas, Costas y Estuarios",
                    "value": 3586.559289086365
                },
                "602c510ffd74967db06639b1": {
                    "name": "Simulación, Diseño, Control y Optimización de Procesos",
                    "value": 1793.2796445431825
                },
                "602c510ffd74967db06639ff": {
                    "name": "Ciencia y Tecnología del Gas y Uso Racional de la Energía",
                    "value": 750
                },
                "602c510ffd74967db0663956": {
                    "name": "Grupo de Investigación en Gestión y Modelación Ambiental",
                    "value": 4445
                },
                "602c510ffd74967db0663990": {
                    "name": "Grupo Mapeo Genético",
                    "value": 376.97849989280576
                },
                "602c510ffd74967db0663a16": {
                    "name": "No lo encontre",
                    "value": 3100
                },
                "602c510ffd74967db0663970": {
                    "name": "Patología Renal y de Trasplantes",
                    "value": 2825
                },
                "602c510ffd74967db06639e9": {
                    "name": "Aerospace Science and Technology ReseArch",
                    "value": 2792.4396001110804
                },
                "602c510ffd74967db0663917": {
                    "name": "Grupo de Investigacion en Farmacologia y Toxicologia \" INFARTO\"",
                    "value": 5146.58644148918
                },
                "602c510ffd74967db06638d6": {
                    "name": "Análisis Multivariado",
                    "value": 975
                },
                "602c510ffd74967db066398b": {
                    "name": "Genética Médica",
                    "value": 2090.3011862842295
                },
                "602c510ffd74967db0663948": {
                    "name": "Grupo de Coloides",
                    "value": 1025
                },
                "602c510ffd74967db06638f3": {
                    "name": "Grupo de Biofísica",
                    "value": 3318.3070664250795
                },
                "602c510ffd74967db0663909": {
                    "name": "Diagnóstico y Control de la Contaminación",
                    "value": 3500
                },
                "602c510ffd74967db06639fd": {
                    "name": "Grupo de Investigación y Gestión sobre Patrimonio",
                    "value": 200
                }
                },
                "publisher": {
                "Hindawi Limited": 81695,
                "BMC": 352120.33776623,
                "Asociación Colombiana de Infectología": 7600,
                "MDPI AG": 336352.0133296308,
                "Public Library of Science (PLoS)": 259525,
                "Frontiers Media S.A.": 235850,
                "Nature Publishing Group": 90946.40866978905,
                "Colégio Brasileiro de Cirurgiões": 185.4154543505559,
                "The Association for Research in Vision and Ophthalmology": 31450,
                "Elsevier": 203307.67999999988,
                "Cambridge University Press": 25278.385141020815,
                "The Journal of Infection in Developing Countries": 3102.0696,
                "Arán Ediciones, S. L.": 19614.96000000001,
                "Fundação de Amparo à Pesquisa do Estado de SP": 1600,
                "BMJ Publishing Group": 48223.376978564826,
                "Wiley": 53579,
                "American Chemical Society": 1500,
                "F1000 Research Ltd": 5000,
                "Universidad de Antioquia": 98100,
                "Universidade de São Paulo": 8457.478178310004,
                "Sociedade Brasileira de Química": 4069.671679274754,
                "Pharmacotherapy Group, University of Benin, Benin City": 2000,
                "American Society for Microbiology": 14400,
                "Association of Support to Oral Health Research (APESB)": 390,
                "Instituto de Investigaciones Agropecuarias, INIA": 650,
                "Tehran University of Medical Sciences": 0,
                "Wolters Kluwer Medknow Publications": 500,
                "Oxford University Press": 21739.34566339612,
                "Fundación Revista Medicina": 0,
                "Iranian Medicinal Plants Society": 215,
                "Universidad Autónoma de Yucatán": 400,
                "Fundação Odontológica de Ribeirão Preto": 101.97849989280574,
                "Facultad de Ciencias Agrarias. Universidad Nacional de Cuyo": 300,
                "Exeley Inc.": 500
                },
                "openaccess": {
                "gold": 1723132.3620811182,
                "closed": 67762.23068810394,
                "bronze": 52978.00656463765,
                "green": 34771.15632984965,
                "hybrid": 48339.07216847288
                }
            },
            "filters": {
                "start_year": 1925,
                "end_year": 2020
            }
        }
        """
        data = self.request.args.get('data')
        tipo = self.request.args.get('type')

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
        elif data=="production":
            idx = self.request.args.get('id')
            max_results=self.request.args.get('max')
            page=self.request.args.get('page')
            start_year=self.request.args.get('start_year')
            end_year=self.request.args.get('end_year')
            sort=self.request.args.get('sort')

            if tipo == None: 
                production=self.get_production(idx,start_year,end_year,sort,"descending")
            else:
                production=self.get_production_by_type(idx,max_results,page,start_year,end_year,sort,"descending",tipo)

            if production:
                response = self.app.response_class(
                response=self.json.dumps(production),
                status=200,
                mimetype='application/json'
                )
            else:
                response = self.app.response_class(
                response=self.json.dumps({"status":"Request returned empty"}),
                status=204,
                mimetype='application/json'
                )
        elif data=="citations":
            idx = self.request.args.get('id')
            start_year=self.request.args.get('start_year')
            end_year=self.request.args.get('end_year')
            citations=self.get_citations(idx,start_year,end_year)
            if citations:
                response = self.app.response_class(
                response=self.json.dumps(citations),
                status=200,
                mimetype='application/json'
                )
            else:
                response = self.app.response_class(
                response=self.json.dumps({"status":"Request returned empty"}),
                status=204,
                mimetype='application/json'
                )
        elif data=="authors":
            idx = self.request.args.get('id')
 
            authors=self.get_authors(idx)
            if authors:
                response = self.app.response_class(
                response=self.json.dumps(authors),
                status=200,
                mimetype='application/json'
                )
            else:
                response = self.app.response_class(
                response=self.json.dumps({"status":"Request returned empty"}),
                status=204,
                mimetype='application/json'
                )

        elif data=="coauthors":
            idx = self.request.args.get('id')

            coauthors=self.get_coauthors(idx)
            if coauthors:
                response = self.app.response_class(
                response=self.json.dumps(coauthors),
                status=200,
                mimetype='application/json'
                )
            else:
                response = self.app.response_class(
                response=self.json.dumps({"status":"Request returned empty"}),
                status=204,
                mimetype='application/json'
                )

        elif data=="csv":
            idx = self.request.args.get('id')
            start_year=self.request.args.get('start_year')
            end_year=self.request.args.get('end_year')
            sort=self.request.args.get('sort')
            production_csv=self.get_csv(idx,start_year,end_year,sort,"descending")
            if production_csv:
                response = self.app.response_class(
                response=production_csv,
                status=200,
                mimetype='text/csv',
                headers={"Content-disposition":
                 "attachment; filename=institutions.csv"}
                )
            else:
                response = self.app.response_class(
                response=self.json.dumps({"status":"Request returned empty"}),
                status=204,
                mimetype='application/json'
                )
        elif data=="json":
            idx = self.request.args.get('id')
            start_year=self.request.args.get('start_year')
            end_year=self.request.args.get('end_year')
            sort=self.request.args.get('sort')
            production_json=self.get_json(idx,start_year,end_year,sort,"descending")
            if production_json:
                response = self.app.response_class(
                response=production_json,
                status=200,
                mimetype='text/plain',
                headers={"Content-disposition":
                 "attachment; filename=institutions.json"}
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

