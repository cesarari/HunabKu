from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from bson import ObjectId
from pymongo import ASCENDING,DESCENDING
from pickle import load
from math import log
from datetime import date
import pandas as pd 

class GroupsApp(HunabkuPluginBase):
    def __init__(self, hunabku):
        super().__init__(hunabku)

    def get_info(self,idx):
        
        result=self.colav_db['documents'].find({"authors.affiliations.branches.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",ASCENDING)]).limit(1)
        if result:
            result=list(result)
            if len(result)>0:
                initial_year=result[0]["year_published"]
        result=self.colav_db['documents'].find({"authors.affiliations.branches.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",DESCENDING)]).limit(1)
        if result:
            result=list(result)
            if len(result)>0:
                final_year=result[0]["year_published"]
        
        filters={
            "start_year":initial_year,
            "end_year":final_year
        }

        group = self.colav_db['branches'].find_one({"type":"group","_id":ObjectId(idx)})
        if group:
            entry={"id":group["_id"],
                "name":group["name"],
                "type":group["type"],
                "abbreviations":"",
                "external_urls":group["external_urls"],
                "institution":[]
            }
            if len(group["abbreviations"])>0:
                entry["abbreviations"]=group["abbreviations"][0]
            inst_id=""
            for rel in group["relations"]:
                if rel["type"]=="university":
                    inst_id=rel["id"]
                    break
            if inst_id:
                inst=self.colav_db['institutions'].find_one({"_id":inst_id})
                if inst:
                    entry["institution"]=[{"name":inst["name"],"id":inst_id,"logo":inst["logo_url"]}]

            return {"data": entry, "filters": filters }
        else:
            return None
    
    def hindex(self,citation_list):
        return sum(x >= i + 1 for i, x in enumerate(sorted(list(citation_list), reverse=True)))

    def get_citations(self,idx=None,start_year=None,end_year=None):


        entry={
            "citations":0,
            "yearly_citations":[],
            "geo":[]
        }

        if start_year:
            try:
                start_year=int(start_year)
                print("start",start_year)
            except:
                print("Could not convert start year to int")
                return None
        if end_year:
            try:
                end_year=int(end_year)
                print("end = ",end_year)
            except:
                print("Could not convert end year to int")
                return None



        pipeline=[
            {"$match":{"authors.affiliations.branches.id":ObjectId(idx)}}
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
                "_id":1
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

    def get_authors(self,idx=None,page=1,max_results=100,sort="citations",direction="descending"):
        if idx:

            pipeline=[
                {"$match":{"authors.affiliations.branches.id":ObjectId(idx)}}
            ]

            pipeline.extend([

                {"$unwind":"$authors"},
                {"$match":{"authors.affiliations.branches.id":ObjectId(idx)}},
                {"$group":{"_id":"$authors.id","papers_count":{"$sum":1},"citations_count":{"$sum":"$citations_count"},"author":{"$first":"$authors"}}},
                {"$sort":{"citations_count":-1}},
                {"$project":{"_id":1,"author.full_name":1,"author.affiliations.name":1,"author.affiliations.id":1,
                    "author.affiliations.branches.name":1,"author.affiliations.branches.type":1,"author.affiliations.branches.id":1,
                    "papers_count":1,"citations_count":1}}



            ])


            total_results = self.colav_db["authors"].count_documents({"branches.id":ObjectId(idx)})


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

            
            skip = (max_results*(page-1))

            pipeline.extend([{"$skip":skip},{"$limit":max_results}])


            #result= self.colav_db["documents"].aggregate(pipeline)
            cursor=self.colav_db["authors"].find({"branches.id":ObjectId(idx)},
                                                {"full_name":1,"affiliations":1,"branches":1,"citations_count":1,"products_count":1})
            cursor=cursor.skip(skip).limit(max_results)

            if sort=="citations" and direction=="ascending":
                cursor.sort([("citations_count",ASCENDING)])
            if sort=="citations" and direction=="descending":
                cursor.sort([("citations_count",DESCENDING)])

        
            entry = []

            for reg in cursor:
                if "branches" in reg.keys():
                    for i in range(len(reg["branches"])):    
                        if reg["branches"][i]["type"]=="group":
                            group_name = reg["branches"][i]["name"]
                            group_id =   reg["branches"][i]["id"]
                        

        
                entry.append({
                    "id":reg["_id"],
                    "name":reg["full_name"],
                    "papers_count":reg["products_count"],
                    "citations_count":reg["citations_count"],
                    "affiliation":{"institution":{"name":reg["affiliations"][0]["name"], 
                                        "id":reg["affiliations"][0]["id"]},
                                   "group":{"name":group_name, "id":group_id}}
                })
            
        return {"total":total_results,"page":page,"count":len(entry),"data":entry}



    def get_coauthors(self,idx=None,start_year=None,end_year=None):
        initial_year=0
        final_year=0

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
            pipeline=[
                {"$match":{"authors.affiliations.branches.id":ObjectId(idx)}}
            ]
 
            if start_year and not end_year:
                pipeline=[
                    {"$match":{"year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)}}
                ]
            elif end_year and not start_year:
                pipeline=[
                    {"$match":{"year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}}
                ]
            elif start_year and end_year:
                pipeline=[
                    {"$match":{"year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}}
                ]
                

        #Meter esto en info
        pipeline.extend([
            {"$unwind":"$authors"},
            {"$group":{"_id":"$authors.id","count":{"$sum":1}}},
            {"$sort":{"count":-1}},
            {"$lookup":{"from":"authors","localField":"_id","foreignField":"_id","as":"author"}},
            {"$project":{"count":1,"author.full_name":1}},
            {"$unwind":"$author"}
        ])

        entry={
            "coauthors":[],
            "geo":[]
        }

        entry["coauthors"]=[
            {"id":reg["_id"],"full_name":reg["author"]["full_name"],"count":reg["count"]} for reg in self.colav_db["documents"].aggregate(pipeline)
        ]

        countries=[]
        country_list=[]
        pipeline=[pipeline[0]]
        pipeline.extend([
            {"$unwind":"$authors"},
            {"$group":{"_id":"$authors.affiliations.id","count":{"$sum":1}}},
            {"$unwind":"$_id"},
            {"$lookup":{"from":"institutions","localField":"_id","foreignField":"_id","as":"affiliation"}},
            {"$project":{"count":1,"affiliation.addresses.country_code":1,"affiliation.addresses.country":1}},
            {"$unwind":"$affiliation"},
            {"$unwind":"$affiliation.addresses"},
            {"$sort":{"count":-1}}
        ])
        for reg in self.colav_db["documents"].aggregate(pipeline):
            if str(reg["_id"])==idx:
                continue
            if not "country_code" in reg["affiliation"]["addresses"].keys():
                continue
            if reg["affiliation"]["addresses"]["country_code"] and reg["affiliation"]["addresses"]["country"]:
                if reg["affiliation"]["addresses"]["country_code"] in country_list:
                    i=country_list.index(reg["affiliation"]["addresses"]["country_code"])
                    countries[i]["count"]+=reg["count"]
                else:
                    country_list.append(reg["affiliation"]["addresses"]["country_code"])
                    countries.append({
                        "country":reg["affiliation"]["addresses"]["country"],
                        "country_code":reg["affiliation"]["addresses"]["country_code"],
                        "count":reg["count"]
                    })
        sorted_geo=sorted(countries,key=lambda x:x["count"],reverse=True)
        countries=sorted_geo
        for item in countries:
            item["log_count"]=log(item["count"])
        entry["geo"]=countries
                        


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

    def get_production_by_type(self,idx=None,max_results=100,page=1,start_year=None,end_year=None,sort=None,direction="descending",tipo=None):

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
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx),
                    "publication_type.type":tipo})

            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx),
                    "publication_type.type":tipo})

            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},
                    "authors.affiliations.branches.id":ObjectId(idx), "publication_type.type":tipo})

            else:
                cursor=self.colav_db['documents'].find({"authors.affiliations.branches.id":ObjectId(idx),"publication_type.type":tipo})


        
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
        return {"total":total,"page":page,"count":len(entry),"data":entry}


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
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)})  },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)})   },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)}) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)}) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)}) }
                ])
            elif end_year and not start_year:
                venn_query={"year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})  },
                    {"type":"gold"  ,"value": self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}) }
                ])
            elif start_year and end_year:
                venn_query={"year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)}) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})}
                ])
            else:
                venn_query={"authors.affiliations.branches.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","authors.affiliations.branches.id":ObjectId(idx)}) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","authors.affiliations.branches.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","authors.affiliations.branches.id":ObjectId(idx)})},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","authors.affiliations.branches.id":ObjectId(idx)})},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","authors.affiliations.branches.id":ObjectId(idx)})}
                ])




        tipos = self.colav_db['documents'].distinct("publication_type.type",{"authors.affiliations.branches.id":ObjectId(idx)})

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
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)})
            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})
            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})
            else:
                cursor=self.colav_db['documents'].find({"authors.affiliations.branches.id":ObjectId(idx)})
        else:
            cursor=self.colav_db['documents'].find()

        if sort=="citations" and direction=="ascending":
            cursor.sort([("citations_count",ASCENDING)])
        if sort=="citations" and direction=="descending":
            cursor.sort([("citations_count",DESCENDING)])
        if sort=="year" and direction=="ascending":
            cursor.sort([("year_published",ASCENDING)])
        if sort=="year" and direction=="descending":
            cursor.sort([("year_published",DESCENDING)])

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
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.affiliations.branches.id":ObjectId(idx)})
            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})
            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.affiliations.branches.id":ObjectId(idx)})
            else:
                cursor=self.colav_db['documents'].find({"authors.affiliations.branches.id":ObjectId(idx)})
        else:
            cursor=self.colav_db['documents'].find()

        if sort=="citations" and direction=="ascending":
            cursor.sort([("citations_count",ASCENDING)])
        if sort=="citations" and direction=="descending":
            cursor.sort([("citations_count",DESCENDING)])
        if sort=="year" and direction=="ascending":
            cursor.sort([("year_published",ASCENDING)])
        if sort=="year" and direction=="descending":
            cursor.sort([("year_published",DESCENDING)])

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
                if "aliases" in au_entry.keys():
                    del(au_entry["aliases"])
                if "national_id" in au_entry.keys():
                    del(au_entry["national_id"])
                affiliations=[]
                for aff in author["affiliations"]:
                    aff_entry=aff
                    aff_db=self.colav_db["institutions"].find_one({"_id":aff["id"]})
                    if aff_db:
                        aff_entry=aff_db
                    if "name_idx" in aff_entry.keys():
                        del(aff_entry["name_idx"])
                    if "addresses" in aff_entry.keys():
                        for add in aff_entry["addresses"]:
                            if "geonames_city" in add.keys():
                                del(add["geonames_city"])
                    if "aliases" in aff_entry.keys():
                        del(aff_entry["aliases"])
                    branches=[]
                    if "branches" in aff.keys():
                        for branch in aff["branches"]:
                            branch_db=self.colav_db["branches"].find_one({"_id":branch["id"]})
                            if branch_db:
                                del(branch_db["aliases"])
                                if "addresses" in branch_db.keys():
                                    for add in branch_db["addresses"]:
                                        del(add["geonames_city"])
                                if "aliases" in branch_db.keys():
                                    del(branch_db["aliases"])
                                branches.append(branch_db)
                    aff_entry["branches"]=branches
                    affiliations.append(aff_entry)
                au_entry["affiliations"]=affiliations
                authors.append(au_entry)
            entry["authors"]=authors
            papers.append(entry)
        return str(papers)



    @endpoint('/app/groups', methods=['GET'])
    def app_groups(self):
        """
        @api {get} /app/groups Groups
        @apiName app
        @apiGroup CoLav app
        @apiDescription Responds with information about a group

        @apiParam {String} apikey Credential for authentication
        @apiParam {String} data (info,production) Whether is the general information or the production
        @apiParam {Object} id The mongodb id of the group requested
        @apiParam {Int} start_year Retrieves result starting on this year
        @apiParam {Int} end_year Retrieves results up to this year
        @apiParam {Int} max Maximum results per page
        @apiParam {Int} page Number of the page
        @apiParam {String} sort (citations,year) Sorts the results by key in descending order

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 204) msg  The HTTP 204 No Content.
        @apiError (Error 200) msg  The HTTP 200 OK.

        @apiSuccessExample {json} Success-Response (data=info):
            HTTP/1.1 200 OK
            {
                "id": "602c50d1fd74967db0663833",
                "name": "Facultad de ciencias exactas y naturales",
                "type": "faculty",
                "external_urls": [
                    {
                    "source": "website",
                    "url": "http://www.udea.edu.co/wps/portal/udea/web/inicio/unidades-academicas/ciencias-exactas-naturales"
                    }
                ],
                "departments": [
                    {
                    "id": "602c50f9fd74967db0663858",
                    "name": "Instituto de matemáticas"
                    }
                ],
                "groups": [
                    {
                    "id": "602c510ffd74967db06639a7",
                    "name": "Modelación con ecuaciones diferenciales"
                    },
                    {
                    "id": "602c510ffd74967db06639ad",
                    "name": "álgebra u de a"
                    }
                ],
                "authors": [
                    {
                    "full_name": "Roberto Cruz Rodes",
                    "id": "5fc5a419b246cc0887190a64"
                    },
                    {
                    "full_name": "Jairo Eloy Castellanos Ramos",
                    "id": "5fc5a4b7b246cc0887190a65"
                    }
                ],
                "institution": [
                    {
                    "name": "University of Antioquia",
                    "id": "60120afa4749273de6161883"
                    }
                ]
                }
        @apiSuccessExample {json} Success-Response (data=production):
            HTTP/1.1 200 OK
            {
                "data": [
                    {
                    "_id": "602ef9dd728ecc2d8e62e030",
                    "title": "Comments on the Riemann conjecture and index theory on Cantorian fractal space-time",
                    "source": {
                        "name": "Chaos Solitons & Fractals",
                        "_id": "602ef9dd728ecc2d8e62e02d"
                    },
                    "authors": [
                        {
                        "full_name": "Carlos Castro",
                        "_id": "602ef9dd728ecc2d8e62e02f",
                        "affiliations": [
                            {
                            "name": "Center for Theoretical Studies, University of Miami",
                            "_id": "602ef9dd728ecc2d8e62e02e",
                            "branches": []
                            }
                        ]
                        },
                        {
                        "full_name": "Jorge Eduardo Mahecha Gomez",
                        "_id": "5fc65863b246cc0887190a9f",
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
                                "name": "Instituto de física",
                                "type": "department",
                                "_id": "602c50f9fd74967db0663859"
                                },
                                {
                                "name": "Grupo de física atómica y molecular",
                                "type": "group",
                                "_id": "602c510ffd74967db06638fb"
                                }
                            ]
                            }
                        ]
                        }
                    ]
                    }
                ],
                "count": 3,
                "page": 1,
                "total_results": 3,
                "initial_year": 2002,
                "final_year": 2014,
                "open_access": {
                    "green": 2,
                    "gold": 0,
                    "bronze": 1,
                    "closed": 0,
                    "hybrid": 0
                },
                "venn_source": {
                    "scholar": 0,
                    "lens": 0,
                    "oadoi": 0,
                    "wos": 0,
                    "scopus": 0,
                    "lens_wos_scholar_scopus": 3
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
            max_results=self.request.args.get('max')
            page=self.request.args.get('page')

            authors = self.get_authors(idx)


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
            start_year=self.request.args.get('start_year')
            end_year=self.request.args.get('end_year')
            coauthors=self.get_coauthors(idx,start_year,end_year)
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
                 "attachment; filename=groups.csv"}
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
                 "attachment; filename=groups.json"}
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

