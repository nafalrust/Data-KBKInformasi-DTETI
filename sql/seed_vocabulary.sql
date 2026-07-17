-- ============================================================
-- Controlled Vocabulary — research_clusters & research_tags
-- Sumber: DataSpecs-WebKBKProject.md §3.3
-- CATATAN: vocabulary v1 awal, boleh berkembang saat cleaning
-- berjalan (lihat Contract §5.4) — perubahan lewat review Lead.
-- ============================================================

INSERT INTO research_clusters (name, slug, description, sort_order) VALUES
    ('Intelligent System and Data', 'intelligent-systems-data', NULL, 1),
    ('Networks, Security, and Infrastructure', 'networks-security-infrastructure', NULL, 2),
    ('IoT, Smart Systems, and Environment', 'iot-smartsystem-environtment', NULL, 3),
    ('Software, Data, and Information Systems', 'software-data-informationsystem', NULL, 4),
    ('Human-Centered Computing and Education', 'humancenteredcomputing-education', NULL, 5);

INSERT INTO research_tags (name, slug, cluster_id, description, is_active)
SELECT t.name, t.slug, c.id, NULL, TRUE
FROM (VALUES
    ('Machine Learning', 'machine-learning', 'intelligent-systems-data'),
    ('Deep Learning', 'deep-learning', 'intelligent-systems-data'),
    ('Data Mining', 'data-mining', 'intelligent-systems-data'),
    ('Computer Vision', 'computer-vision', 'intelligent-systems-data'),
    ('NLP', 'nlp', 'intelligent-systems-data'),
    ('Artificial Intelligence', 'artificial-intelligence', 'intelligent-systems-data'),

    ('Computer Networks', 'computer-networks', 'networks-security-infrastructure'),
    ('Cybersecurity', 'cybersecurity', 'networks-security-infrastructure'),
    ('Digital Forensics', 'digital-forensics', 'networks-security-infrastructure'),
    ('Blockchain', 'blockchain', 'networks-security-infrastructure'),

    ('IoT', 'iot', 'iot-smartsystem-environtment'),
    ('Smart City', 'smart-city', 'iot-smartsystem-environtment'),
    ('Context-Aware Computing', 'context-aware-computing', 'iot-smartsystem-environtment'),
    ('Automation', 'automation', 'iot-smartsystem-environtment'),

    ('Software Engineering', 'software-engineering', 'software-data-informationsystem'),
    ('Website', 'website', 'software-data-informationsystem'),
    ('Mobile App', 'mobile-app', 'software-data-informationsystem'),
    ('Database', 'database', 'software-data-informationsystem'),

    ('Human-Computer Interaction', 'human-computer-interaction', 'humancenteredcomputing-education'),
    ('UI', 'ui', 'humancenteredcomputing-education'),
    ('UX', 'ux', 'humancenteredcomputing-education'),
    ('E-Learning', 'e-learning', 'humancenteredcomputing-education'),
    ('Immersive Technology', 'immersive-technology', 'humancenteredcomputing-education')
) AS t(name, slug, cluster_slug)
JOIN research_clusters c ON c.slug = t.cluster_slug;
