#!/usr/bin/env python3
"""
Generate dcat-entry.ttl -- DCAT-AP-NL 3.0 catalogus entry for the BRP.

Conform: DCAT-AP-NL 3.0 (https://docs.geostandaarden.nl/dcat/dcat-ap-nl30/)
Based on: https://data.overheid.nl/dataset/basisregistratie-personen-bpr-donl
"""

import os

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import XSD, SKOS

from namespaces import (
    new_graph, save,
    BRP, BRPAUT,
    RDF, RDFS, DCTERMS, FOAF,
    ODRL, DCAT, DCATAP, VCARD, ADMS, ELI,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, "ttl", "dcat-entry.ttl")

# --- Shared URIRefs ---

# Organisations (TOOI identifiers)
ORG_RVIG = URIRef("https://identifier.overheid.nl/tooi/id/oorg/oorg10103")
ORG_KOOP = URIRef("https://identifier.overheid.nl/tooi/id/organisatie/koop")

# BRP-specific URIs
CONTACT_RVIG = URIRef("https://data.rijksoverheid.nl/brp/contact/rvig")
DATASET_BRP = URIRef("https://data.overheid.nl/dataset/basisregistratie-personen-bpr-donl")
CATALOG_BRP = URIRef("https://data.rijksoverheid.nl/brp/catalogus")

# Services en distributie (geen eigen namespace — eenmalig gebruik)
SVC_ADHOC = URIRef("https://data.rijksoverheid.nl/brp/service/adhoc")
SVC_SPONTAAN = URIRef("https://data.rijksoverheid.nl/brp/service/spontaan")
SVC_SELECTIE = URIRef("https://data.rijksoverheid.nl/brp/service/selectie")
DIST_GBAV = URIRef("https://data.rijksoverheid.nl/brp/distributie/gbav")

# Legislation
WET_BRP = URIRef("https://wetten.overheid.nl/BWBR0033715")

# EU controlled vocabularies
LANG_NLD = URIRef("http://publications.europa.eu/resource/authority/language/NLD")
COUNTRY_NLD = URIRef("http://publications.europa.eu/resource/authority/country/NLD")
ACCESS_NON_PUBLIC = URIRef("http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC")
FREQ_DAILY = URIRef("http://publications.europa.eu/resource/authority/frequency/DAILY")
THEME_GOVE = URIRef("http://publications.europa.eu/resource/authority/data-theme/GOVE")
STATUS_COMPLETED = URIRef("http://publications.europa.eu/resource/authority/dataset-status/COMPLETED")
LICENSE_NOT_OPEN = URIRef("http://standaarden.overheid.nl/owms/terms/geslotenlicentie")

# OWMS theme (NL-specific, naast EU theme)
OWMS_BESTUUR = URIRef("http://standaarden.overheid.nl/owms/terms/Bestuur")


def main():
    print(f"Generating {OUTPUT_PATH}...")
    g = new_graph()

    # Remove unused namespace bindings
    for prefix in ["brpds", "brpsvc", "brpelm", "brpcat", "brpgrp",
                    "brpafn", "brpnat", "brpland", "brpvbt", "gem",
                    "tpl", "prov", "owl", "skos", "rdf"]:
        try:
            g.namespace_manager.bind(prefix, None, override=True, replace=True)
        except Exception:
            pass

    # =========================================================================
    # Catalogus (DCAT-AP-NL 3.0 §5.1)
    # =========================================================================

    g.add((CATALOG_BRP, RDF.type, DCAT.Catalog))
    g.add((CATALOG_BRP, DCTERMS.title, Literal(
        "BRP Autorisatiecatalogus", lang="nl")))
    g.add((CATALOG_BRP, DCTERMS.description, Literal(
        "Catalogus van de Basisregistratie Personen (BRP) met autorisatiebesluiten "
        "als ODRL policies. Bevat de dataset BRP en de bijbehorende "
        "verstrekkingsvoorzieningen als DCAT DataServices.", lang="nl")))
    g.add((CATALOG_BRP, DCTERMS.publisher, ORG_RVIG))
    g.add((CATALOG_BRP, DCTERMS.language, LANG_NLD))
    g.add((CATALOG_BRP, DCAT.dataset, DATASET_BRP))
    g.add((CATALOG_BRP, DCAT.service, SVC_ADHOC))
    g.add((CATALOG_BRP, DCAT.service, SVC_SPONTAAN))
    g.add((CATALOG_BRP, DCAT.service, SVC_SELECTIE))

    # =========================================================================
    # Organisaties
    # =========================================================================

    g.add((ORG_RVIG, RDF.type, FOAF.Organization))
    g.add((ORG_RVIG, FOAF.name, Literal(
        "Rijksdienst voor Identiteitsgegevens", lang="nl")))
    g.add((ORG_RVIG, FOAF.homepage, URIRef("https://www.rvig.nl")))

    g.add((ORG_KOOP, RDF.type, FOAF.Organization))
    g.add((ORG_KOOP, FOAF.name, Literal(
        "Kennis- en Exploitatiecentrum voor Officiele Overheidspublicaties",
        lang="nl")))

    # =========================================================================
    # Contactpunt (vcard:Kind — DCAT-AP-NL 3.0 verplicht)
    # =========================================================================

    g.add((CONTACT_RVIG, RDF.type, VCARD.Organization))
    g.add((CONTACT_RVIG, VCARD.fn, Literal(
        "Rijksdienst voor Identiteitsgegevens", lang="nl")))
    g.add((CONTACT_RVIG, VCARD.hasURL, URIRef("https://www.rvig.nl/brp")))
    g.add((CONTACT_RVIG, VCARD.hasEmail, URIRef("mailto:info@rvig.nl")))

    # =========================================================================
    # Dataset: Basisregistratie Personen (DCAT-AP-NL 3.0 §5.2)
    #
    # Based on https://data.overheid.nl/dataset/basisregistratie-personen-bpr-donl
    # =========================================================================

    ds = DATASET_BRP
    g.add((ds, RDF.type, DCAT.Dataset))

    # --- Verplicht (Required per DCAT-AP-NL 3.0) ---

    g.add((ds, DCTERMS.title, Literal(
        "Basisregistratie Personen (BRP)", lang="nl")))

    g.add((ds, DCTERMS.description, Literal(
        "De Nederlandse overheid registreert persoonsgegevens in de "
        "Basisregistratie Personen (BRP). Alle overheidsinstellingen en "
        "bestuursorganen zijn verplicht voor hun taken gebruik te maken van "
        "deze gegevens. De BRP bevat persoonsgegevens van inwoners van "
        "Nederland (ingezetenen) en van personen die Nederland hebben "
        "verlaten of die korter dan 4 maanden in Nederland wonen. "
        "De BRP is GEEN open data.", lang="nl")))

    g.add((ds, DCTERMS.identifier, Literal(
        "http://data.overheid.nl/dataset/basisregistratie-personen-bpr-donl")))

    g.add((ds, DCTERMS.publisher, ORG_KOOP))
    g.add((ds, DCTERMS.creator, ORG_RVIG))
    g.add((ds, DCAT.contactPoint, CONTACT_RVIG))

    # Theme: EU Data Theme vocabulary (verplicht) + OWMS (aanbevolen)
    g.add((ds, DCAT.theme, THEME_GOVE))
    g.add((ds, DCAT.theme, OWMS_BESTUUR))

    g.add((ds, DCTERMS.accessRights, ACCESS_NON_PUBLIC))

    # --- Aanbevolen (Recommended) ---

    for kw in [
        "Persoonsgegevens", "Basisregistratie", "BRP",
        "Adres", "Identiteit", "Natuurlijk persoon",
        "Woonadres in Nederland", "Briefadres in Nederland",
        "Adres buitenland", "Kind", "Ouder", "Partner",
    ]:
        g.add((ds, DCAT.keyword, Literal(kw, lang="nl")))

    g.add((ds, DCTERMS.language, LANG_NLD))
    g.add((ds, DCTERMS.spatial, COUNTRY_NLD))

    g.add((ds, DCTERMS.conformsTo, URIRef(
        "https://data.rijksoverheid.nl/brp/def")))

    g.add((ds, DCAT.landingPage, URIRef(
        "https://www.rvig.nl/basisregistratie-personen")))

    g.add((ds, FOAF.page, URIRef("https://www.rvig.nl/brp")))
    g.add((ds, FOAF.page, URIRef(
        "https://data.overheid.nl/dataset/basisregistratie-personen-bpr-donl")))
    g.add((ds, FOAF.page, URIRef(
        "https://www.digitaleoverheid.nl/dossiers/brp/")))

    # Temporal coverage
    temporal = BNode()
    g.add((ds, DCTERMS.temporal, temporal))
    g.add((temporal, RDF.type, DCTERMS.PeriodOfTime))
    g.add((temporal, DCAT.startDate, Literal(
        "2014-01-06", datatype=XSD.date)))

    # --- Optioneel ---

    g.add((ds, DCTERMS.accrualPeriodicity, FREQ_DAILY))
    g.add((ds, DCTERMS.issued, Literal("2014-01-06", datatype=XSD.date)))
    g.add((ds, DCTERMS.modified, Literal("2022-04-05", datatype=XSD.date)))
    g.add((ds, ADMS.status, STATUS_COMPLETED))
    g.add((ds, DCTERMS.type, URIRef(
        "http://inspire.ec.europa.eu/metadata-codelist/ResourceType/dataset")))

    # Provenance
    prov = BNode()
    g.add((ds, DCTERMS.provenance, prov))
    g.add((prov, RDF.type, DCTERMS.ProvenanceStatement))
    g.add((prov, RDFS.label, Literal(
        "De BRP is de opvolger van de Gemeentelijke Basisadministratie "
        "persoonsgegevens (GBA). Op 6 januari 2014 is de Wet BRP in "
        "werking getreden ter vervanging van de Wet GBA.", lang="nl")))

    g.add((ds, DCTERMS.relation, URIRef(
        "https://www.stelselcatalogus.nl/registraties/brp")))

    # --- Conditioneel (toepasselijke wetgeving) ---

    g.add((ds, DCATAP.applicableLegislation, WET_BRP))

    # --- Distributie ---

    g.add((ds, DCAT.distribution, DIST_GBAV))

    # =========================================================================
    # Wet BRP als ELI LegalResource
    # =========================================================================

    g.add((WET_BRP, RDF.type, ELI.LegalResource))
    g.add((WET_BRP, DCTERMS.title, Literal(
        "Wet basisregistratie personen", lang="nl")))
    g.add((WET_BRP, ELI.id_local, Literal("BWBR0033715")))

    # =========================================================================
    # DataServices (koppelvlakken) — DCAT-AP-NL 3.0 §5.4
    # =========================================================================

    # Ad hoc (HaalCentraal BRP Bevragen API)
    svc = SVC_ADHOC
    g.add((svc, RDF.type, DCAT.DataService))
    g.add((svc, DCTERMS.title, Literal(
        "BRP Ad hoc gegevensverstrekking", lang="nl")))
    g.add((svc, DCTERMS.description, Literal(
        "Zoekvraag-gebaseerde verstrekking van persoonsgegevens op verzoek "
        "van een geautoriseerde afnemer. Geimplementeerd als de HaalCentraal "
        "BRP Bevragen API.", lang="nl")))
    g.add((svc, DCAT.endpointURL, URIRef(
        "https://brp.basisregistraties.overheid.nl/haalcentraal/api/brp")))
    g.add((svc, DCAT.servesDataset, ds))
    g.add((svc, DCTERMS.conformsTo, URIRef(
        "https://brp-api.github.io/Haal-Centraal-BRP-bevragen/")))
    g.add((svc, DCTERMS.accessRights, ACCESS_NON_PUBLIC))
    g.add((svc, DCTERMS.publisher, ORG_RVIG))

    # Spontaan
    svc = SVC_SPONTAAN
    g.add((svc, RDF.type, DCAT.DataService))
    g.add((svc, DCTERMS.title, Literal(
        "BRP Spontane gegevensverstrekking", lang="nl")))
    g.add((svc, DCTERMS.description, Literal(
        "Push-gebaseerde verstrekking van persoonsgegevens. Bij wijziging van "
        "sleutelrubrieken op een persoonslijst die aan de voorwaarderegel "
        "voldoet, worden gegevens automatisch aan de afnemer verstrekt via "
        "de Berichtendienst.", lang="nl")))
    g.add((svc, DCAT.endpointURL, URIRef(
        "https://brp.basisregistraties.overheid.nl/berichtendienst")))
    g.add((svc, DCAT.servesDataset, ds))
    g.add((svc, DCTERMS.accessRights, ACCESS_NON_PUBLIC))
    g.add((svc, DCTERMS.publisher, ORG_RVIG))

    # Selectie
    svc = SVC_SELECTIE
    g.add((svc, RDF.type, DCAT.DataService))
    g.add((svc, DCTERMS.title, Literal(
        "BRP Selectieverstrekking", lang="nl")))
    g.add((svc, DCTERMS.description, Literal(
        "Periodieke of eenmalige selectie van persoonslijsten die aan de "
        "voorwaarderegel voldoen. Geselecteerde gegevens worden verstrekt "
        "of afnemersindicaties worden geplaatst/verwijderd.", lang="nl")))
    g.add((svc, DCAT.endpointURL, URIRef(
        "https://brp.basisregistraties.overheid.nl/selectie")))
    g.add((svc, DCAT.servesDataset, ds))
    g.add((svc, DCTERMS.accessRights, ACCESS_NON_PUBLIC))
    g.add((svc, DCTERMS.publisher, ORG_RVIG))

    # =========================================================================
    # Distributie: BRP Verstrekkingsvoorziening (DCAT-AP-NL 3.0 §5.3)
    # =========================================================================

    dist = DIST_GBAV
    g.add((dist, RDF.type, DCAT.Distribution))

    # Verplicht
    g.add((dist, DCAT.accessURL, URIRef("https://www.rvig.nl/brp")))
    g.add((dist, DCTERMS.license, LICENSE_NOT_OPEN))

    # Aanbevolen
    g.add((dist, DCTERMS.title, Literal(
        "BRP Verstrekkingsvoorziening (GBA-V)", lang="nl")))
    g.add((dist, DCTERMS.description, Literal(
        "De centrale verstrekkingsvoorziening van de BRP (GBA-V). "
        "Alle gegevensverstrekking — ad hoc, spontaan en selectie — loopt "
        "via deze voorziening. Toegang is uitsluitend voor geautoriseerde "
        "afnemers op basis van een autorisatiebesluit conform de Wet BRP.",
        lang="nl")))
    g.add((dist, DCAT.accessService, SVC_ADHOC))
    g.add((dist, DCAT.accessService, SVC_SPONTAAN))
    g.add((dist, DCAT.accessService, SVC_SELECTIE))
    g.add((dist, DCTERMS.conformsTo, URIRef(
        "https://data.rijksoverheid.nl/brp/def")))

    # Conditioneel (niet-publieke service)
    rights = BNode()
    g.add((dist, DCTERMS.rights, rights))
    g.add((rights, RDF.type, DCTERMS.RightsStatement))
    g.add((rights, RDFS.label, Literal(
        "Toegang uitsluitend voor geautoriseerde afnemers op basis van een "
        "autorisatiebesluit conform de Wet BRP. Welke rubrieken via welk "
        "koppelvlak verstrekt mogen worden is per afnemer vastgelegd in "
        "de autorisatietabel (Tabel 35).", lang="nl")))
    g.add((dist, DCATAP.applicableLegislation, WET_BRP))

    # Optioneel: link naar autorisatiebesluiten
    g.add((dist, ODRL.hasPolicy, BRPAUT.autorisatiebesluiten))

    save(g, OUTPUT_PATH)
    print(f"Generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
