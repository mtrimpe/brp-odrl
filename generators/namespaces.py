"""Shared RDF namespaces and utilities for all BRP-ODRL generators."""

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, XSD, OWL, SKOS, DCTERMS, PROV, FOAF

# BRP namespaces
BRP = Namespace("https://data.rijksoverheid.nl/brp/def#")
BRPCAT = Namespace("https://data.rijksoverheid.nl/brp/categorie/")
BRPGRP = Namespace("https://data.rijksoverheid.nl/brp/groep/")
BRPELM = Namespace("https://data.rijksoverheid.nl/brp/element/")
BRPRUB = Namespace("https://data.rijksoverheid.nl/brp/rubriek/")
BRPAFN = Namespace("https://data.rijksoverheid.nl/brp/afnemer/")
BRPAUT = Namespace("https://data.rijksoverheid.nl/brp/autorisatie/")
BRPNAT = Namespace("https://data.rijksoverheid.nl/brp/nationaliteit/")
BRPLAND = Namespace("https://data.rijksoverheid.nl/brp/land/")
BRPVBT = Namespace("https://data.rijksoverheid.nl/brp/verblijfstitel/")
BRPDS = Namespace("https://data.rijksoverheid.nl/brp/distributie/")
BRPSVC = Namespace("https://data.rijksoverheid.nl/brp/service/")

# External namespaces
ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
TPL = Namespace("http://www.w3.org/ns/odrl/2/temporal/")
GEM = Namespace("https://identifier.overheid.nl/tooi/id/gemeente/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCATAP = Namespace("http://data.europa.eu/r5r/")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
ADMS = Namespace("http://www.w3.org/ns/adms#")
ELI = Namespace("http://data.europa.eu/eli/ontology#")


def new_graph():
    """Create a new Graph with all standard BRP-ODRL namespace bindings."""
    g = Graph()
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)
    g.bind("owl", OWL)
    g.bind("skos", SKOS)
    g.bind("dct", DCTERMS)
    g.bind("prov", PROV)
    g.bind("foaf", FOAF)
    g.bind("odrl", ODRL)
    g.bind("tpl", TPL)
    g.bind("brp", BRP)
    g.bind("brpcat", BRPCAT)
    g.bind("brpgrp", BRPGRP)
    g.bind("brpelm", BRPELM)
    g.bind("brprub", BRPRUB)
    g.bind("brpafn", BRPAFN)
    g.bind("brpaut", BRPAUT)
    g.bind("brpnat", BRPNAT)
    g.bind("brpland", BRPLAND)
    g.bind("brpvbt", BRPVBT)
    g.bind("brpds", BRPDS)
    g.bind("brpsvc", BRPSVC)
    g.bind("gem", GEM)
    g.bind("dcat", DCAT)
    g.bind("dcatap", DCATAP)
    g.bind("vcard", VCARD)
    g.bind("adms", ADMS)
    g.bind("eli", ELI)
    return g


def save(g, path):
    """Serialize a graph to Turtle and print stats."""
    g.serialize(destination=path, format="turtle")
    print(f"  {path}: {len(g)} triples")
