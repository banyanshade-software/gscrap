#!/usr/bin/env python3
# coding: utf-8

from lxml import html
import re
import requests
import time
import datetime
import unicodedata
import locale
import sys


# web get is done in fr, and had been tested in fr only
stdLocale = locale.setlocale(locale.LC_ALL, 'fr_FR')
normalLocale = locale.getlocale()



# see also:
# https://github.com/SimonGuilbert/Genealogy/blob/ffc07311252426481c10f60e74cb05c5e97e1e90/backend/webScraping.py


#page = requests.get('file://t.html')
#tree = html.fromstring(page.content)


# https://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-normalize-in-a-python-unicode-string/517974#517974
def remove_accents_(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nfkd_form.encode('ASCII', 'ignore')
    return only_ascii


def get_byclass(tree, cl):
    xp = '//span[@class="'+cl+'"]/a/text()'
    val = tree.xpath(xp)[0].strip()
    return val


class GWS_DatePlace:
    def __init__(self, date=None, place=None, string=None, comma=0):
        self.dateprefix = ""
        self.place = None
        self.date = None
        self.datefmt = '%d %b %Y' # for strftime
        if string == None:
            self.date = date
            self.place = place
        else:
            # parse string
            # "Décédé le 3 novembre 1990 - Bormes-les-Mimosas, 83019, Var, Provence-Alpes-Côte d'Azur, France, à l'âge de 75 ans"
            # Deceased 16 August 1931 - Saint-Amand-les-Eaux, 59526, Nord, Nord-Pas-de-Calais, France, aged 75 years old
            print('parse: "'+string+'"')
            #replace &nbsp; (unicode 0xA0)
            string = string.replace(u'\xa0', u' ')
            # skip if single word (ex: "décédée$")
            if len(string.split(" ", 1)) < 2:
                print(f'singleword "{string}"')
                return None
            #remove first word
            string = re.sub(r"^[^ ]* ", "", string)
            print('   -> :', string)
            string = re.sub(r"^le\s", "", string)
            print('   -> :', string)
            #remove à l'age de ... or aged...
            string = re.sub(r"à l'âge d.*$", "", string)
            string = re.sub(r"aged.*$", "", string)
            string = re.sub(r",$", "", string)
            string = re.sub(r",\s$", "", string)
            if comma == 0:
                print('split on : ', string)
                if string[0]=='-':
                    v = string.split("- ", 1)
                else:
                    v = string.split(" - ", 1)
            else:
                print('comma split on : ', string)
                v = string.split(",", 1)
                print(v)
            dt = v[0].strip(' \t\n')
            if len(v) > 1 :
                pl = v[1].strip(' \t\n')
                # remove trailing ", France" (ugly)
                pl = re.sub(r", France$", "", pl)
            else:
                pl = None
            print('date  "'+dt+'"')
            if pl is not None: print('place "'+pl+'"')
            self.place = pl
            #dta = remove_accents(dt)
            dta = dt.replace(u'\xa0', u' ')
            dta = dta.replace('1er ', '1 ')
            if dta.startswith("vers "):
                self.dateprefix = "ABT "
                dta = dta[5:]
                print(f'data ABT "{dta}"')
            elif dta.startswith("entre le "):
                # keep only first date, and use AFT... not perfect but only few indi got this
                self.dateprefix = "AFT "
                dta = dta[9:].split(" et ")[0]
            elif dta.startswith("entre "):
                # keep only first date, and use AFT... not perfect but only few indi got this
                self.dateprefix = "AFT "
                dta = dta[6:].split(" et ")[0]
            elif dta.startswith("peut-être le "):
                self.dateprefix = "EST"
                dta = dta[13:]
            elif dta.startswith("après "):
                self.dateprefix = "AFT "
                dta = dta[6:]
            elif dta.startswith("avant "):
                self.dateprefix = "BEF "
                dta = dta[6:]
            elif dta.startswith("en "):
                print(f'start_en {dta}')
                dta = dta[3:]
            dta1 = dta
            dta = re.sub(r" \([^)]*\)", "", dta)
            print(f'suppr parenthese "{dta1}" -> "{dta}"')
            #print('locale:', locale.getlocale())
            if len(dta)>0:
                try:
                    date =  datetime.datetime.strptime(dta, "%d %B %Y")
                except:
                    try :
                        date =  datetime.datetime.strptime(dta, "%B %Y")
                        self.datefmt = '%b %Y' # for strftime
                    except:
                        try :
                            date =  datetime.datetime.strptime(dta, "%Y")
                            self.datefmt = '%Y' # for strftime
                        except:
                            print(f'cant parse date {dta}')
                            if comma != 0:
                                # Marié, Elliant, 29049, Finistère, Bretagne, France, avec Françoise Le Bourhis 1720-1771 dont
                                self.date = None
                                print(f'place only ? "{string}"')
                                self.place = string
                            else:
                                exit(1)
                print('date: ', dt, ' -> ', dta, ' -> ', date, type(date))
                self.date = date

    def _produceGedcom(self, f):
        if self.date is not None: 
            locale.setlocale(locale.LC_ALL, 'en_US')
            d = self.date.strftime(self.datefmt) # '%d %b %Y')
            print(f'2 DATE {self.dateprefix}{d}', file=f)
            locale.setlocale(locale.LC_ALL, normalLocale)
        if self.place is not None: 
            print(f'2 PLAC {self.place}', file=f)


#
# ----------------------------------------------------
#
class GWS_Tree:
    def __init__(self, base="https://gw.geneanet.org/", maxlevel=1):
        self.pending = []
        self.level = 0
        self.baseurl = base
        self.maxlevel = maxlevel
        #self.rootPerson = None
        self.knownPersons = {}
    
    def addPersonWithUrl(self, url, lev):
        if url in self.knownPersons: 
            k = self.knownPersons[url]
            print('known ', url)
            return k
        print('add l=', lev,' url ', url)
        if lev > self.maxlevel:
            print('--- max level')
            return None
        if 'http:/' in url or 'https:/' in url :
            u = url
        else:
            u = self.baseurl + url
        p = GWS_Person(self, url=u, level=lev)
        self.pending.append(p)
        self.knownPersons[url] = p
        return p

    def _dumpPending(self):
        for p in self.pending:
            print('   pending Person: ', p.url)
    
    def urlPending(self):
        return [ p.url for p in self.pending]

    def dumpPending(self):
        print(self.urlPending())

    def processPending(self):
        tl = self.pending
        self.pending = []
        r = False
        for p in tl:
            p.loadFromUrl()
            r = True
        return r

    def produceGedcom(self, f):
        self._gedcomHeader(f)
        for url,p in self.knownPersons.items():
            print('prod')
            print(p)
            p._produceGedcom(f)
        self._gedcomFooter(f)

    def _gedcomHeader(self, f):
        print(f'0 HEAD', file=f)
        print(f'1 SOUR geneanet', file=f)
        print(f'1 CHAR UTF-8', file=f)
        print(f'0 @N9999@ NOTE non vérifié (importé)', file=f)

    def _gedcomFooter(self, f):
        print(f'0 TRLR', file=f)
    

#
# ----------------------------------------------------
#
class GWS_Person:
    personCount = 0

    def __init__(self, gwstree, url=None, level=0):
        self.num = GWS_Person.personCount
        GWS_Person.personCount = GWS_Person.personCount + 1
        self.firstname = ""
        self.gender = "?"
        self.lastname = ""
        self.profession = None 
        self.birth = None
        self.death = None
        self.gtree = gwstree
        self.parent1 = None
        self.parent2 = None
        self.conjoint = None
        self.marriage = None
        self.children = []
        self.url = url
        self.level = level
        print('======= Person ', self.num, '   level=', self.level)

    def loadFromUrl(self):
        print('load url = ', self.url)
        t = requests.get(self.url, headers={'Accept':'text/html', 'Host':'gw.geneanet.org','User-Agent':'Mozilla/5.0', 'Accept-Language':'fr-fr'})
        print(t.request)
        print('resp:')
        print(t)
        tree = html.fromstring(t.content)
        print(tree)
        self.loadFromHtml(tree)
        return self

    def loadFromHtml(self, tree):
        # name
        self.firstname = tree.xpath('//span[@class="gw-individual-info-name-firstname"]/a/text()')[0].strip()
        self.lastname =  tree.xpath('//span[@class="gw-individual-info-name-lastname"]/a/text()')[0].strip()
        print('name:'+self.firstname+':'+self.lastname+':')
        # gender
        s = tree.xpath('//div[@id="person-title"]//img/@alt')
        print(type(s))
        if s[0] == 'H':
            self.gender = 'M'
        elif s[0] == 'F':
            self.gender = 'F'
        print('gender:', s, '->', self.gender)

        infos = tree.xpath('(//div[@id="perso"]//div[@id="person-title"]/..//ul)[1]/li/text()')
        for inf in infos:
            t = inf.strip()
            first = t.split(' ')[0]
            if first in ["Né", "Née", "Born"]:
                print("naissance")
                self.birth = GWS_DatePlace(string=t)
            elif first in ["Décédé", "Décédée", "Deceased"]:
                print("décès")
                self.death = GWS_DatePlace(string=t)
            elif first == "":
                #print("vide")
                continue
            else:
                print("autre")
                self.profession = t

            print('----')
            print('<<<'+t+'>>>')
        # unions (but not for root person). We actually assume single union (no test case for several)
        if self.level > 0: # not for root person
            uns = tree.xpath('//ul[@class="fiche_union"]/li')
            # process each union
            for un in uns:
                print('---- union ----')
                print(type(un))
                print(un)
                dtl = un.xpath('./em')
                if len(dtl)>0:
                    dt = dtl[0]
                    print('dt mariage')
                    print(dt.text_content())
                    self.marriage = GWS_DatePlace(string=dt.text_content(), comma=1)
                else:
                    dt = None # date of marriage unknown
                hr = un.xpath('./a')[0]
                print('hr')
                print(hr)
                url = hr.get("href")
                print('url')
                print(url)
                self.conjoint = self.gtree.addPersonWithUrl(url, self.level)           
                break # only one union
        
        prs = tree.xpath('(//div[@id="perso"]//div[@id="person-title"]/..//ul)[1]/following-sibling::ul[not(@class)]/li/a')
        print('---- parents ----')
        #print(type(prs))
        print(prs)
        n = 0
        for p in prs:
            print('--- par')
            if n > 1: break
            #print(html.tostring(p))
            url = p.get("href")
            print(url)
            if n==0 :
                self.parent1 = self.gtree.addPersonWithUrl(url, self.level+1)
            elif n==1 :
                self.parent2 = self.gtree.addPersonWithUrl(url, self.level+1)
                if self.parent2 is not None:
                    self.parent2.addChild(self)
                break
            n = n+1
        print('---- done ----')
        return self

    def addChild(self, c):
        self.children.append(c)

    def _produceGedcom(self, f):
        # INDIvidue record
        print(f'0 @I{self.num}@ INDI', file=f)
        print(f'1 NAME {self.firstname} /{self.lastname}/', file=f)
        print(f'1 SEX {self.gender}', file=f)
        if self.birth is not None:
            print(f'1 BIRT', file=f)
            self.birth._produceGedcom(f)
        if self.death is not None:
            print(f'1 DEAT', file=f)
            self.death._produceGedcom(f)
        print(f'1 NOTE @N{self.num}@', file=f)
        print(f'1 NOTE @N9999@', file=f)
        if self.profession is not None:
            # gramps specific (?)
            print(f'1 FACT {self.profession}', file=f)
            print(f'2 TYPE Occupation', file=f)
        if self.conjoint is not None:
            if self.gender == 'M':
                fid = self.conjoint
            else:
                fid = self
            print(f'1 FAMS @F{fid.num}@', file=f)
        if self.parent2 is not None:
            print(f'1 FAMC @F{self.parent2.num}@', file=f)
        # import note (using same number)
        print(f'0 @N{self.num}@ NOTE importé de {self.url}', file=f)
        # FAMS record, on wife only, using wife number
        if self.gender != 'M' and self.conjoint is not None:
            print(f'0 @F{self.num}@ FAM', file=f)
            print(f'1 HUSB @I{self.conjoint.num}@', file=f)
            print(f'1 WIFE @I{self.num}@', file=f)
            if self.marriage is not None:
                print(f'1 MARR', file=f)
                self.marriage._produceGedcom(f)
            for c in self.children:
                print(f'1 CHIL @I{c.num}@', file=f)
            

# ----------------------------------------------------------

if len(sys.argv) != 3 : 
    print(f'usage: {sys.argv[0]} maxlevel geneanet_url')
    exit(1)

maxlevel = int(sys.argv[1])
print(f'max level: {maxlevel}')
gt = GWS_Tree(maxlevel=maxlevel)
rootperson  = gt.addPersonWithUrl(sys.argv[2], 0)


#tree = html.parse('t.html')
#gt.rootPerson = GWS_Person(gt,level=0).loadFromHtml(tree)
#print("hop")
#print(gt.rootPerson)
#print(gt.rootPerson.firstname)
#print(type(gt.rootPerson.firstname))

print('----------')
print('----------')
gt.dumpPending()
#exit(1)

while True:
    print('------------------ proc pending')
    gt.dumpPending()
    r = gt.processPending()
    print(r)
    if not r: 
        break
print('----------')
gt.dumpPending()
print('----------')
print('----------')
f = open('gedcom.ged','w')
print('gedcom:')
print(f)

gt.produceGedcom(f)

