from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from bson import ObjectId
from pymongo import ASCENDING,DESCENDING
from pickle import load
from math import log
from datetime import date


class AuthorsApp(HunabkuPluginBase):
    def __init__(self, hunabku):
        super().__init__(hunabku)

    def get_info(self,idx):
        initial_year=0
        final_year=0

        if idx:
            result=self.colav_db['documents'].find({"authors.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",ASCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    initial_year=result[0]["year_published"]
            result=self.colav_db['documents'].find({"authors.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",DESCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    final_year=result[0]["year_published"]

        filters={
            "start_year":initial_year,
            "end_year":final_year
        }


        author = self.colav_db['authors'].find_one({"_id":ObjectId(idx)})
        if author:
            entry={
                "id":author["_id"],
                "name":author["full_name"],
                "affiliation":{"institution":{"name":"","id":""},"group":{"name":"","id":""}},
                "external_urls":[],
                "logo":""
            }
            if "affiliations" in author.keys():
                if len(author["affiliations"]):
                    entry["affiliation"]["institution"]["id"]=author["affiliations"][-1]["id"]
                    entry["affiliation"]["institution"]["name"]=author["affiliations"][-1]["name"]
            
            if entry["affiliation"]:
                inst_db=self.colav_db["institutions"].find_one({"_id":ObjectId(entry["affiliation"]["institution"]["id"])})
                if inst_db:
                    #entry["country_code"]=inst_db["addresses"][0]["country_code"]
                    #entry["country"]=inst_db["addresses"][0]["country"]
                    entry["logo"]=inst_db["logo_url"]

            if "branches" in author.keys():
                for i in range(len(author["branches"])):
                    if author["branches"][i]["type"]=="group":
                        entry["affiliation"]["group"]["id"]  =author["branches"][i]["id"]
                        entry["affiliation"]["group"]["name"]=author["branches"][i]["name"]




            sources=[]
            for ext in author["external_ids"]:

                if ext["source"]=="researchid" and not "researcherid" in sources:
                    sources.append("researcherid")
                    entry["external_urls"].append({
                        "source":"researcherid",
                        "url":"https://publons.com/researcher/"+ext["value"]})
                if ext["source"]=="scopus" and not "scopus" in sources:
                    sources.append("scopus")
                    entry["external_urls"].append({
                        "source":"scopus",
                        "url":"https://www.scopus.com/authid/detail.uri?authorId="+ext["value"]})
                if ext["source"]=="scholar" and not "scholar" in sources:
                    sources.append("scholar")
                    entry["external_urls"].append({
                        "source":"scholar",
                        "url":"https://scholar.google.com.co/citations?user="+ext["value"]})
                if ext["source"]=="orcid" and not "orcid" in sources:
                    sources.append("orcid")
                    entry["external_urls"].append({
                        "source":"orcid",
                        "url":"https://orcid.org/"+ext["value"]})


                        
                        


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
            {"$match":{"authors.id":ObjectId(idx)}}
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
                {"$match":{"authors.id":ObjectId(idx)}}
            ]


            if start_year and not end_year:
                pipeline=[
                    {"$match":{"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}}
                ]
            elif end_year and not start_year:
                pipeline=[
                    {"$match":{"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}}
                ]
            elif start_year and end_year:
                pipeline=[
                    {"$match":{"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}}
                ]
                


        pipeline.extend([
            {"$unwind":"$authors"},
            {"$unwind":"$authors.affiliations"},
            {"$group":{"_id":"$authors.id","count":{"$sum":1}}},
            {"$sort":{"count":-1}},
            {"$lookup":{"from":"authors","localField":"_id","foreignField":"_id","as":"author"}},
            {"$project":{"count":1,"author.full_name":1}},
            {"$unwind":"$author"}
        ])

        entry={
            "coauthors":[],
            "geo":[],
            "coauthors_network":{}
        }

        entry["coauthors"]=[
            {"id":reg["_id"],"full_name":reg["author"]["full_name"],"count":reg["count"]} for reg in self.colav_db["documents"].aggregate(pipeline) if reg["_id"] != ObjectId(idx)
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

        nodes=[]
        edges=[]

        nodes_idlist=[]
        edge_tuples=[]
        arango_edges=[]
        arango_nodes=[]
        arango_mongo_nodes={}
        query="FOR c IN authors FILTER c.mongo_id=='"+idx+"' RETURN {_id:c._id,name:c.name,affiliation:c.affiliation}"
        result=list(self.arangodb.AQLQuery(query,rawResults=True,batchSize=1))
        if result:
            arangoid=result[0]["_id"]
            nodes.append({
                    "id":idx,
                    "degree":0,
                    "size":0,
                    "label":result[0]["name"],
                    "affiliation":result[0]["affiliation"]["name"],
                })
            query="FOR v,e,p IN 1..1 ANY '"+arangoid+"' GRAPH coauthors RETURN {affiliation:v.affiliation,mongo_id:v.mongo_id,_id:v._id,name:v.name,weight:e.weight}" 
            for vertex in self.arangodb.AQLQuery(query,rawResults=True,batchSize=1):
                arango_nodes.append(vertex["_id"])
                
                arango_mongo_nodes[vertex["_id"]]=vertex["mongo_id"]
                aff_name=""
                if vertex["affiliation"]:
                    aff_name=vertex["affiliation"]["name"]
                node={
                    "id":vertex["mongo_id"],
                    "degree":0,
                    "size":0,
                    "affiliation":aff_name,
                    "label":vertex["name"]
                }
                if not node in nodes:
                    nodes.append(node)
                normal=(idx,vertex["mongo_id"])
                rever=(vertex["mongo_id"],idx)
                if not (normal in edge_tuples or rever in edge_tuples):
                    edge_tuples.append(normal)
                    edges.append({
                        "coauthorships":vertex["weight"],
                        "source":idx,
                        "sourceName":result[0]["name"],
                        "target":vertex["mongo_id"],
                        "targetName":vertex["name"],
                        "size":vertex["weight"]
                    })

            for node in arango_nodes:
                query="FOR e IN coauthorship FILTER e._from=='"+node+"' RETURN {_from:e._from,_to:e._to,weight:e.weight}"
                for res in self.arangodb.AQLQuery(query,rawResults=True,batchSize=1):
                    if res["_to"] in arango_nodes and res["_from"] in arango_nodes:
                        if res["_to"]==res["_from"]:
                            continue
                        normal=(arango_mongo_nodes[res["_from"]],arango_mongo_nodes[res["_to"]])
                        rever=(arango_mongo_nodes[res["_to"]],arango_mongo_nodes[res["_from"]])
                        if not (normal in edge_tuples or rever in edge_tuples):
                            edge_tuples.append(normal)
                            #edges.append({"from":arango_mongo_nodes[res["_from"]],"to":arango_mongo_nodes[res["_to"]],"coauthorships":res["weight"]})
                            edges.append({
                                "coauthorships":res["weight"],
                                "source":arango_mongo_nodes[res["_from"]],
                                "sourceName":"",
                                "target":arango_mongo_nodes[res["_to"]],
                                "targetName":"",
                                "size":res["weight"]
                            })
            del(arango_nodes)
            del(arango_mongo_nodes)
            del(edge_tuples)
            total=max([e["coauthorships"] for e in edges]) if len(edges)>0 else 1
            degrees={}
            num_nodes=len(nodes)
            for edge in edges:
                edge["coauthorships"]=edge["coauthorships"]
                edge["size"]=10*log(1+edge["coauthorships"]/total,2)
                if edge["source"] in degrees.keys():
                    degrees[edge["source"]]+=1
                else:
                    degrees[edge["source"]]=1
                if edge["target"] in degrees.keys():
                    degrees[edge["target"]]+=1
                else:
                    degrees[edge["target"]]=1
            for node in nodes:
                if node["id"] in degrees.keys():
                    node["size"]=50*log(1+degrees[node["id"]]/(num_nodes-1),2)
                    node["degree"]=degrees[node["id"]]
            entry["coauthors_network"]={"nodes":nodes,"edges":edges}
        else:
            au=self.colav_db["authors"].find_one({"_id":idx})
            aff=""
            if au:
                if "affiliations" in au.keys():
                    if len(au["affiliations"])>0:
                        aff=au["affiliations"][0]

            entry["coauthors_network"]={"nodes":[{
                "id":idx,
                "degree":0,
                "size":10,
                "label":au["full_name"] if aff!="" else "",
                "affiliation":aff["name"] if aff!="" else "",
            }],"edges":[]}


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

    def get_production(self,idx=None,max_results=100,page=1,start_year=None,end_year=None,sort=None,direction=None):
        papers=[]
        total=0
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
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})
                venn_query={"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})  },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})   },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}) }
                ])
            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})
                venn_query={"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})  },
                    {"type":"gold"  ,"value": self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}) },
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}) },
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}) }
                ])
            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})
                venn_query={"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})}
                ])
            else:
                cursor=self.colav_db['documents'].find({"authors.id":ObjectId(idx)})
                venn_query={"authors.id":ObjectId(idx)}
                open_access.extend([
                    {"type":"green" ,"value":self.colav_db['documents'].count_documents({"open_access_status":"green","authors.id":ObjectId(idx)}) },
                    {"type":"gold"  ,"value":self.colav_db['documents'].count_documents({"open_access_status":"gold","authors.id":ObjectId(idx)})  },
                    {"type":"bronze","value":self.colav_db['documents'].count_documents({"open_access_status":"bronze","authors.id":ObjectId(idx)})},
                    {"type":"closed","value":self.colav_db['documents'].count_documents({"open_access_status":"closed","authors.id":ObjectId(idx)})},
                    {"type":"hybrid","value":self.colav_db['documents'].count_documents({"open_access_status":"hybrid","authors.id":ObjectId(idx)})}
                ])
        else:
            cursor=self.colav_db['documents'].find() 
            venn_query={}
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

        for paper in cursor:
            entry={
                "id":paper["_id"],
                "title":paper["titles"][0]["title"],
                "citations_count":paper["citations_count"],
                "year_published":paper["year_published"],
                "open_access_status":paper["open_access_status"]
            }

            source=self.colav_db["sources"].find_one({"_id":paper["source"]["id"]})
            if source:
                entry["source"]={"name":source["title"],"id":str(source["_id"])}
            authors=[]
            for author in paper["authors"]:
                au_entry={}
                author_db=self.colav_db["authors"].find_one({"_id":author["id"]})
                if author_db:
                    au_entry={"full_name":author_db["full_name"],"id":author_db["_id"]}
                affiliations=[]
                for aff in author["affiliations"]:
                    aff_entry={}
                    group_entry={}
                    aff_db=self.colav_db["institutions"].find_one({"_id":aff["id"]})
                    if aff_db:
                        aff_entry={"name":aff_db["name"],"id":aff_db["_id"]}
                    branches=[]
                    if "branches" in aff.keys():
                        for branch in aff["branches"]:
                            if "id" in branch.keys():
                                branch_db=self.colav_db["branches"].find_one({"_id":branch["id"]})
                                if branch_db and branch_db["type"] != "department" and branch_db["type"]!="faculty":
                                    group_entry= ({"name":branch_db["name"],"type":branch_db["type"],"id":branch_db["_id"]})
                                    affiliations.append(group_entry)

                    affiliations.append(aff_entry)
                au_entry["affiliations"]=affiliations
                authors.append(au_entry)
            entry["authors"]=authors
            papers.append(entry)

        tipos = self.colav_db['documents'].distinct("publication_type.type",{"authors.id":ObjectId(idx)})

        return {
            "open_access":open_access,
            "venn_source":self.get_venn(venn_query),
            "types":tipos

            }

        """
        return {
            "data":papers,
            "count":len(papers),
            "page":page,
            "total":total,
            "venn_source":self.get_venn(venn_query),
            "open_access":open_access,

        }
        """
    def get_production_by_type(self,idx=None,max_results=100,page=1,start_year=None,end_year=None,sort=None,direction=None,tipo=None):
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
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.id":ObjectId(idx),
                    "publication_type.type":tipo})

            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.id":ObjectId(idx),
                    "publication_type.type":tipo})

            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},
                    "authors.id":ObjectId(idx), "publication_type.type":tipo})

            else:
                cursor=self.colav_db['documents'].find({"authors.id":ObjectId(idx),"publication_type.type":tipo})


        
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
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})
            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})
            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})
            else:
                cursor=self.colav_db['documents'].find({"authors.id":ObjectId(idx)})
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
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})
            elif end_year and not start_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})
            elif start_year and end_year:
                cursor=self.colav_db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})
            else:
                cursor=self.colav_db['documents'].find({"authors.id":ObjectId(idx)})
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

    @endpoint('/app/authors', methods=['GET'])
    def app_authors(self):
       
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
        elif data=="production":
            idx = self.request.args.get('id')
            max_results=self.request.args.get('max')
            page=self.request.args.get('page')
            start_year=self.request.args.get('start_year')
            end_year=self.request.args.get('end_year')
            sort=self.request.args.get('sort')
            tipo = self.request.args.get('type')

            if tipo == None: 
                production=self.get_production(idx,max_results,page,start_year,end_year,sort,"descending")
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
                 "attachment; filename=authors.csv"}
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
                 "attachment; filename=authors.json"}
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
