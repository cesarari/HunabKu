from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from bson import ObjectId
from pymongo import ASCENDING,DESCENDING
from pickle import load
from math import log
from datetime import date
import pymongo


class AuthorsApp(HunabkuPluginBase):
    def __init__(self, hunabku):
        super().__init__(hunabku)

        client = pymongo.MongoClient("mongodb://localhost:27017")

        self.db = client.colombia

    def get_info(self,idx):

        author = self.db['authors'].find_one({"_id":ObjectId(idx)})

        author = self.db['authors'].find_one({"_id":ObjectId(idx)})
        if author:
            entry={"id":author["_id"],
                "full_name":author["full_name"],
                "type":"author",
                "affiliation":[],
                "country":"",
                "country_code":"",
                "faculty":{},
                "department":{},
                "group":{},
                "external_urls":[],
            }
            if "affiliations" in author.keys():
                if len(author["affiliations"]):
                    entry["affiliation"]=author["affiliations"][-1]
            if entry["affiliation"]:
                inst_db=self.db["institutions"].find_one({"_id":ObjectId(entry["affiliation"]["id"])})
                if inst_db:
                    entry["country_code"]=inst_db["addresses"][0]["country_code"]
                    entry["country"]=inst_db["addresses"][0]["country"]
                    entry["logo"]=inst_db["logo_url"]
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

            for branch in author["branches"]:
                if branch["type"]=="faculty":
                    entry["faculty"]=branch
                elif branch["type"]=="department":
                    entry["department"]=branch
                elif branch["type"]=="group":
                    entry["group"]=branch

            return entry
        else:
            return None

    def hindex(self,citation_list):
        return sum(x >= i + 1 for i, x in enumerate(sorted(list(citation_list), reverse=True)))
    
    def get_citations(self,idx=None,start_year=None,end_year=None):
        initial_year=0
        final_year=0

        entry={
            "citations":0,
            "H5":0,
            "H":0,
            "yearly_citations":{}
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
        if idx:
            result=self.db['documents'].find({"authors.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",ASCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    initial_year=result[0]["year_published"]
            result=self.db['documents'].find({"authors.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",DESCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    final_year=result[0]["year_published"]

            pipeline=[
                    {"$match":{"authors.id":ObjectId(idx)}}
            ]
            if start_year and not end_year:
                cites_pipeline=[
                    {"$match":{"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}}
                ]
            elif end_year and not start_year:
                cites_pipeline=[
                    {"$match":{"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}}
                ]
            elif start_year and end_year:
                cites_pipeline=[
                    {"$match":{"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}}
                ]
            else:
                cites_pipeline=[
                    {"$match":{"authors.id":ObjectId(idx)}}
                ]
        
        else:
            pipeline=[]
            cites_pipeline=[]
            result=self.db['documents'].find({},{"year_published":1}).sort([("year_published",ASCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    initial_year=result[0]["year_published"]
            result=self.db['documents'].find({},{"year_published":1}).sort([("year_published",DESCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    final_year=result[0]["year_published"]

        pipeline.extend([
            {"$project":{
                "_id":0,"year_published":1,"citations_count":1,"citations":1
            }}
        ])

        cites5_list=[]
        cites_list=[]
        now=date.today()
        for idx,reg in enumerate(self.db["documents"].aggregate(pipeline)):
            if reg["year_published"]<now.year:
                cites_list.append(reg["citations_count"])
                if reg["year_published"]>now.year-5:
                    cites5_list.append(reg["citations_count"])
        entry["H5"]=self.hindex(cites5_list)
        entry["H"]=self.hindex(cites_list)

        
        cites_pipeline.extend([
            {"$unwind":"$citations"},
            {"$lookup":{
                "from":"documents",
                "localField":"citations",
                "foreignField":"_id",
                "as":"citation"}
            },
            {"$unwind":"$citation"},
            {"$project":{"citation.year_published":1}},
            {"$group":{
                "_id":"$citation.year_published","count":{"$sum":1}}
            },
            {"$sort":{
                "_id":-1
            }}
        ])

        for idx,reg in enumerate(self.db["documents"].aggregate(cites_pipeline)):
            entry["citations"]+=reg["count"]
            entry["yearly_citations"][reg["_id"]]=reg["count"]

        filters={
            "start_year":initial_year,
            "end_year":final_year
        }
        return {"data":entry,"filters":filters}



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
        venn_source["scholar"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":"lens"},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["lens"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":"wos"},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["wos"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":"scopus"}]
        venn_source["scopus"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":"lens"},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["scholar_lens"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":"wos"},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["scholar_wos"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":"scopus"}]
        venn_source["scholar_scopus"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":"lens"},
                {"source_checked.source":"wos"},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["lens_wos"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":"lens"},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":"scopus"}]
        venn_source["lens_scopus"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":"wos"},
                {"source_checked.source":"scopus"}]
        venn_source["wos_scopus"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":"lens"},
                {"source_checked.source":"wos"},
                {"source_checked.source":{"$ne":"scopus"}}]
        venn_source["scholar_lens_wos"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":{"$ne":"lens"}},
                {"source_checked.source":"wos"},
                {"source_checked.source":"scopus"}]
        venn_source["scholar_wos_scopus"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":"lens"},
                {"source_checked.source":{"$ne":"wos"}},
                {"source_checked.source":"scopus"}]
        venn_source["scholar_lens_scopus"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":{"$ne":"scholar"}},
                {"source_checked.source":"lens"},
                {"source_checked.source":"wos"},
                {"source_checked.source":"scopus"}]
        venn_source["lens_wos_scopus"]=self.db['documents'].count_documents(venn_query)
        venn_query["$and"]=[{"source_checked.source":"scholar"},
                {"source_checked.source":"lens"},
                {"source_checked.source":"wos"},
                {"source_checked.source":"scopus"}]
        venn_source["scholar_lens_wos_scopus"]=self.db['documents'].count_documents(venn_query)

        return venn_source

    def get_production(self,idx=None,max_results=100,page=1,start_year=None,end_year=None,sort=None,direction=None):
        papers=[]
        initial_year=9999
        final_year=0
        total=0
        open_access={}
        
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
            result=self.db['documents'].find({"authors.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",ASCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    initial_year=result[0]["year_published"]
            result=self.db['documents'].find({"authors.id":ObjectId(idx)},{"year_published":1}).sort([("year_published",DESCENDING)]).limit(1)
            if result:
                result=list(result)
                if len(result)>0:
                    final_year=result[0]["year_published"]
            if start_year and not end_year:
                cursor=self.db['documents'].find({"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})
                venn_query={"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}
                open_access={"green":self.db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}),
                    "gold":self.db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}),
                    "bronze":self.db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}),
                    "closed":self.db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)}),
                    "hybrid":self.db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})}
            elif end_year and not start_year:
                cursor=self.db['documents'].find({"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})
                venn_query={"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}
                open_access={"green":self.db['documents'].count_documents({"open_access_status":"green","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}),
                    "gold":self.db['documents'].count_documents({"open_access_status":"gold","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}),
                    "bronze":self.db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}),
                    "closed":self.db['documents'].count_documents({"open_access_status":"closed","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)}),
                    "hybrid":self.db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})}
            elif start_year and end_year:
                cursor=self.db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})
                venn_query={"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}
                open_access={"green":self.db['documents'].count_documents({"open_access_status":"green","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}),
                    "gold":self.db['documents'].count_documents({"open_access_status":"gold","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}),
                    "bronze":self.db['documents'].count_documents({"open_access_status":"bronze","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}),
                    "closed":self.db['documents'].count_documents({"open_access_status":"closed","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)}),
                    "hybrid":self.db['documents'].count_documents({"open_access_status":"hybrid","year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})}
            else:
                cursor=self.db['documents'].find({"authors.id":ObjectId(idx)})
                venn_query={"authors.id":ObjectId(idx)}
                open_access={"green":self.db['documents'].count_documents({"open_access_status":"green","authors.id":ObjectId(idx)}),
                    "gold":self.db['documents'].count_documents({"open_access_status":"gold","authors.id":ObjectId(idx)}),
                    "bronze":self.db['documents'].count_documents({"open_access_status":"bronze","authors.id":ObjectId(idx)}),
                    "closed":self.db['documents'].count_documents({"open_access_status":"closed","authors.id":ObjectId(idx)}),
                    "hybrid":self.db['documents'].count_documents({"open_access_status":"hybrid","authors.id":ObjectId(idx)})}
        else:
            cursor=self.db['documents'].find() 
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

            source=self.db["sources"].find_one({"_id":paper["source"]["id"]})
            if source:
                entry["source"]={"name":source["title"],"id":str(source["_id"])}
            authors=[]
            for author in paper["authors"]:
                au_entry={}
                author_db=self.db["authors"].find_one({"_id":author["id"]})
                if author_db:
                    au_entry={"full_name":author_db["full_name"],"id":author_db["_id"]}
                affiliations=[]
                for aff in author["affiliations"]:
                    aff_entry={}
                    aff_db=self.db["institutions"].find_one({"_id":aff["id"]})
                    if aff_db:
                        aff_entry={"name":aff_db["name"],"id":aff_db["_id"]}
                    branches=[]
                    if "branches" in aff.keys():
                        for branch in aff["branches"]:
                            if "id" in branch.keys():
                                branch_db=self.db["branches"].find_one({"_id":branch["id"]})
                                if branch_db:
                                    branches.append({"name":branch_db["name"],"type":branch_db["type"],"id":branch_db["_id"]})
                    aff_entry["branches"]=branches
                    affiliations.append(aff_entry)
                au_entry["affiliations"]=affiliations
                authors.append(au_entry)
            entry["authors"]=authors
            papers.append(entry)
        if initial_year==9999:
            initial_year=0
        return {
            "data":papers,
            "count":len(papers),
            "page":page,
            "total_results":total,
            "venn_source":self.get_venn(venn_query),
            "open_access":open_access,
            "filters":{
                "start_year":initial_year,
                "end_year":final_year
            }
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
                cursor=self.db['documents'].find({"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})
            elif end_year and not start_year:
                cursor=self.db['documents'].find({"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})
            elif start_year and end_year:
                cursor=self.db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})
            else:
                cursor=self.db['documents'].find({"authors.id":ObjectId(idx)})
        else:
            cursor=self.db['documents'].find()

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

            source=self.db["sources"].find_one({"_id":paper["source"]["id"]})
            if source:
                csv_text+="\t"+source["title"].replace("\t","").replace("\n","").replace("\r","")
                csv_text+="\t"+source["publisher"]
                serial_entry=""
                for serial in source["serials"]:
                    if serial["type"]=="issn" or serial["type"]=="eissn" or serial["type"]=="pissn":
                        serial_entry=serial["value"]
                csv_text+="\t"+serial_entry

            csv_text+="\t"+str(paper["authors"][0]["id"])
            author_db=self.db["authors"].find_one({"_id":paper["authors"][0]["id"]})
            if author_db:
                csv_text+="\t"+author_db["full_name"]
            else:
                csv_text+="\t"+""
            aff_db=""
            if "affiliations" in paper["authors"][0].keys():
                if len(paper["authors"][0]["affiliations"])>0:
                    csv_text+="\t"+str(paper["authors"][0]["affiliations"][0]["id"])
                    aff_db=self.db["institutions"].find_one({"_id":paper["authors"][0]["affiliations"][0]["id"]})
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
                cursor=self.db['documents'].find({"year_published":{"$gte":start_year},"authors.id":ObjectId(idx)})
            elif end_year and not start_year:
                cursor=self.db['documents'].find({"year_published":{"$lte":end_year},"authors.id":ObjectId(idx)})
            elif start_year and end_year:
                cursor=self.db['documents'].find({"year_published":{"$gte":start_year,"$lte":end_year},"authors.id":ObjectId(idx)})
            else:
                cursor=self.db['documents'].find({"authors.id":ObjectId(idx)})
        else:
            cursor=self.db['documents'].find()

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
            source=self.db["sources"].find_one({"_id":paper["source"]["id"]})
            if source:
                entry["source"]=source
            authors=[]
            for author in paper["authors"]:
                au_entry=author
                author_db=self.db["authors"].find_one({"_id":author["id"]})
                if author_db:
                    au_entry=author_db
                affiliations=[]
                for aff in author["affiliations"]:
                    aff_entry=aff
                    aff_db=self.db["institutions"].find_one({"_id":aff["id"]})
                    if aff_db:
                        aff_entry=aff_db
                    branches=[]
                    if "branches" in aff.keys():
                        for branch in aff["branches"]:
                            branch_db=self.db["branches"].find_one({"_id":branch["id"]}) if "id" in branch.keys() else ""
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
            production=self.get_production(idx,max_results,page,start_year,end_year,sort,"descending")
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