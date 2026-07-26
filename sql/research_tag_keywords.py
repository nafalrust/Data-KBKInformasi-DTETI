# Kamus keyword untuk matching judul/abstract publikasi -> research_tags (seed_vocabulary.sql)
# Dipakai untuk generate KANDIDAT tag per dosen (draft), bukan assignment final.
# Semua keyword dicek case-insensitive, substring match, terhadap teks judul (+abstract kalau ada).
# Urutan tidak berpengaruh; hindari keyword super pendek/umum (mis. "ai", "ui", "ux") yang gampang
# match kata lain secara tidak sengaja -- pakai word-boundary saat load, bukan substring polos.

TAG_KEYWORDS = {
    # --- Intelligent System and Data ---
    "machine-learning": [
        "machine learning", "pembelajaran mesin", "supervised learning",
        "unsupervised learning", "reinforcement learning", "random forest",
        "support vector machine", "svm", "decision tree", "gradient boosting",
        "xgboost", "regression model", "classification model",
    ],
    "deep-learning": [
        "deep learning", "pembelajaran mendalam", "neural network",
        "jaringan saraf tiruan", "cnn", "convolutional neural network",
        "recurrent neural network", "rnn", "lstm", "transformer",
        "generative adversarial network", "gan", "autoencoder",
    ],
    "data-mining": [
        "data mining", "penambangan data", "association rule",
        "clustering", "klasterisasi", "text mining", "pattern recognition",
        "knowledge discovery",
    ],
    "computer-vision": [
        "computer vision", "image processing", "pengolahan citra",
        "object detection", "image classification", "image segmentation",
        "facial recognition", "pengenalan wajah", "optical character recognition",
        "ocr",
    ],
    "nlp": [
        "natural language processing", "nlp", "text classification",
        "sentiment analysis", "analisis sentimen", "named entity recognition",
        "text summarization", "chatbot", "language model", "word embedding",
        "part-of-speech",
    ],
    "artificial-intelligence": [
        "artificial intelligence", "kecerdasan buatan", "expert system",
        "sistem pakar", "fuzzy logic", "genetic algorithm", "algoritma genetika",
        "intelligent system",
    ],

    # --- Networks, Security, and Infrastructure ---
    "computer-networks": [
        "computer network", "jaringan komputer", "routing", "tcp/ip",
        "network topology", "wireless network", "software defined network",
        "sdn", "network performance", "quality of service", "qos",
        "vpn", "protokol jaringan",
    ],
    "cybersecurity": [
        "cybersecurity", "cyber security", "keamanan siber", "keamanan jaringan",
        "network security", "intrusion detection", "malware", "penetration testing",
        "vulnerability", "kerentanan", "enkripsi", "cryptography", "kriptografi",
        "phishing", "firewall",
    ],
    "digital-forensics": [
        "digital forensics", "forensik digital", "network forensics",
        "mobile forensics", "cyber forensics", "chain of custody",
    ],
    "blockchain": [
        "blockchain", "smart contract", "cryptocurrency", "distributed ledger",
        "ethereum", "bitcoin", "consensus algorithm",
    ],

    # --- IoT, Smart Systems, and Environment ---
    "iot": [
        "internet of things", "iot", "sensor network", "wireless sensor",
        "embedded system", "sistem tertanam", "mqtt", "raspberry pi", "arduino",
    ],
    "smart-city": [
        "smart city", "kota cerdas", "smart building", "smart transportation",
        "smart parking", "urban computing",
    ],
    "context-aware-computing": [
        "context-aware", "context aware computing", "pervasive computing",
        "ubiquitous computing",
    ],
    "automation": [
        "automation", "otomasi", "automatic control", "kontrol otomatis",
        "robotics", "robotika", "plc", "scada", "industrial automation",
    ],

    # --- Software, Data, and Information Systems ---
    "software-engineering": [
        "software engineering", "rekayasa perangkat lunak", "software testing",
        "software architecture", "software quality", "agile", "requirement engineering",
        "software development life cycle", "sdlc", "microservices",
    ],
    "website": [
        "web application", "aplikasi web", "website development",
        "sistem informasi berbasis web", "web-based information system",
        "e-commerce", "content management system",
    ],
    "mobile-app": [
        "mobile application", "aplikasi mobile", "android application",
        "ios application", "mobile app development", "cross-platform mobile",
    ],
    "database": [
        "database", "basis data", "database design", "sql", "nosql",
        "data warehouse", "database management system", "query optimization",
    ],

    # --- Human-Centered Computing and Education ---
    "human-computer-interaction": [
        "human-computer interaction", "human computer interaction", "hci",
        "interaksi manusia komputer", "usability testing", "usability",
    ],
    "ui": [
        "user interface", "antarmuka pengguna", "interface design",
    ],
    "ux": [
        "user experience", "pengalaman pengguna", "ux design", "ux research",
    ],
    "e-learning": [
        "e-learning", "electronic learning", "pembelajaran daring",
        "pembelajaran online", "learning management system", "lms",
        "media pembelajaran", "distance learning", "blended learning",
    ],
    "immersive-technology": [
        "virtual reality", "vr", "augmented reality", "ar",
        "mixed reality", "immersive technology", "realitas virtual",
        "realitas tertambah", "metaverse",
    ],
}
