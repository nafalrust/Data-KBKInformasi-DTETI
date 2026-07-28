# Peta tag_slug -> cluster_slug, mengikuti sql/seed_vocabulary.sql.
# Dipakai db/generate_research_cluster_candidates.py untuk menurunkan cluster
# dari tag dengan skor tertinggi per dosen.

TAG_TO_CLUSTER = {
    "machine-learning": "intelligent-systems-data",
    "deep-learning": "intelligent-systems-data",
    "data-mining": "intelligent-systems-data",
    "computer-vision": "intelligent-systems-data",
    "nlp": "intelligent-systems-data",
    "artificial-intelligence": "intelligent-systems-data",

    "computer-networks": "networks-security-infrastructure",
    "cybersecurity": "networks-security-infrastructure",
    "digital-forensics": "networks-security-infrastructure",
    "blockchain": "networks-security-infrastructure",

    "iot": "iot-smartsystem-environtment",
    "smart-city": "iot-smartsystem-environtment",
    "context-aware-computing": "iot-smartsystem-environtment",
    "automation": "iot-smartsystem-environtment",

    "software-engineering": "software-data-informationsystem",
    "website": "software-data-informationsystem",
    "mobile-app": "software-data-informationsystem",
    "database": "software-data-informationsystem",

    "human-computer-interaction": "humancenteredcomputing-education",
    "ui": "humancenteredcomputing-education",
    "ux": "humancenteredcomputing-education",
    "e-learning": "humancenteredcomputing-education",
    "immersive-technology": "humancenteredcomputing-education",
}
