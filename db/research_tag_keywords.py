# Kamus keyword untuk matching judul/abstract publikasi -> research_tags (seed_vocabulary.sql)
# Dipakai untuk generate KANDIDAT tag per dosen (draft), bukan assignment final.
# Semua keyword dicek case-insensitive, substring match, terhadap teks judul (+abstract kalau ada).
# Urutan tidak berpengaruh; hindari keyword super pendek/umum (mis. "ai", "ui", "ux") yang gampang
# match kata lain secara tidak sengaja -- pakai word-boundary saat load, bukan substring polos.

TAG_KEYWORDS = {
    # --- Intelligent System and Data ---
    "machine-learning": [
        "machine learning", "pembelajaran mesin", "supervised learning",
        "unsupervised learning", "semi-supervised learning", "reinforcement learning",
        "random forest", "support vector machine", "svm", "decision tree",
        "gradient boosting", "xgboost", "lightgbm", "regression model",
        "classification model", "k-nearest neighbor", "knn", "naive bayes",
        "ensemble learning", "feature selection", "feature engineering",
        "hyperparameter tuning", "cross validation", "predictive model",
        "model prediksi", "algoritma pembelajaran", "k-means",
        "logistic regression", "linear regression", "adaboost",
    ],
    "deep-learning": [
        "deep learning", "pembelajaran mendalam", "neural network",
        "jaringan saraf tiruan", "artificial neural network", "ann",
        "cnn", "convolutional neural network", "recurrent neural network",
        "rnn", "lstm", "gru", "transformer", "attention mechanism",
        "generative adversarial network", "gan", "autoencoder",
        "transfer learning", "backpropagation", "resnet", "mobilenet",
        "yolo", "u-net", "bert", "diffusion model", "self-supervised learning",
    ],
    "data-mining": [
        "data mining", "penambangan data", "association rule",
        "clustering", "klasterisasi", "text mining", "pattern recognition",
        "knowledge discovery", "market basket analysis", "outlier detection",
        "deteksi anomali", "anomaly detection", "big data analytics",
        "data preprocessing", "apriori algorithm",
    ],
    "computer-vision": [
        "computer vision", "image processing", "pengolahan citra",
        "object detection", "image classification", "image segmentation",
        "facial recognition", "pengenalan wajah", "optical character recognition",
        "ocr", "image recognition", "pengenalan citra", "citra digital",
        "video processing", "pose estimation", "semantic segmentation",
        "image enhancement", "edge detection",
    ],
    "nlp": [
        "natural language processing", "nlp", "text classification",
        "sentiment analysis", "analisis sentimen", "named entity recognition",
        "text summarization", "chatbot", "language model", "word embedding",
        "part-of-speech", "text mining", "information retrieval",
        "topic modeling", "speech recognition", "pengenalan ucapan",
        "text generation", "question answering", "word2vec", "tf-idf",
    ],
    "artificial-intelligence": [
        "artificial intelligence", "kecerdasan buatan", "expert system",
        "sistem pakar", "fuzzy logic", "logika fuzzy", "genetic algorithm",
        "algoritma genetika", "intelligent system", "sistem cerdas",
        "swarm intelligence", "particle swarm optimization", "ant colony optimization",
        "metaheuristic", "optimization algorithm", "algoritma optimasi",
        "decision support system", "sistem pendukung keputusan",
    ],

    # --- Networks, Security, and Infrastructure ---
    "computer-networks": [
        "computer network", "jaringan komputer", "routing", "tcp/ip",
        "network topology", "wireless network", "software defined network",
        "sdn", "network performance", "quality of service", "qos",
        "vpn", "protokol jaringan", "network protocol", "load balancing",
        "network architecture", "local area network", "wide area network",
        "manet", "mobile ad hoc network", "5g network", "network simulation",
        "ns2", "ns3", "bandwidth management", "network monitoring",
    ],
    "cybersecurity": [
        "cybersecurity", "cyber security", "keamanan siber", "keamanan jaringan",
        "network security", "intrusion detection", "intrusion prevention",
        "malware", "penetration testing", "vulnerability", "kerentanan",
        "enkripsi", "encryption", "cryptography", "kriptografi",
        "phishing", "firewall", "authentication", "autentikasi",
        "access control", "ddos", "denial of service", "security threat",
        "ancaman keamanan", "data privacy", "privasi data",
    ],
    "digital-forensics": [
        "digital forensics", "forensik digital", "network forensics",
        "mobile forensics", "cyber forensics", "chain of custody",
        "forensik jaringan", "forensik komputer", "computer forensics",
        "digital evidence", "bukti digital", "incident response",
    ],
    "blockchain": [
        "blockchain", "smart contract", "cryptocurrency", "distributed ledger",
        "ethereum", "bitcoin", "consensus algorithm", "decentralized application",
        "dapp", "nft", "non-fungible token", "hyperledger", "web3",
    ],

    # --- IoT, Smart Systems, and Environment ---
    "iot": [
        "internet of things", "iot", "sensor network", "wireless sensor",
        "embedded system", "sistem tertanam", "mqtt", "raspberry pi", "arduino",
        "esp32", "esp8266", "microcontroller", "mikrokontroler",
        "smart sensor", "sensor cerdas", "rfid", "lora", "lorawan",
        "zigbee", "smart device", "perangkat pintar",
    ],
    "smart-city": [
        "smart city", "kota cerdas", "smart building", "smart transportation",
        "smart parking", "urban computing", "smart grid", "smart farming",
        "smart agriculture", "pertanian cerdas", "smart home", "rumah pintar",
        "smart lighting", "traffic management", "manajemen lalu lintas",
    ],
    "context-aware-computing": [
        "context-aware", "context aware computing", "pervasive computing",
        "ubiquitous computing", "location-based service", "layanan berbasis lokasi",
        "ambient intelligence", "context awareness",
    ],
    "automation": [
        "automation", "otomasi", "automatic control", "kontrol otomatis",
        "robotics", "robotika", "plc", "programmable logic controller",
        "scada", "industrial automation", "otomasi industri", "control system",
        "sistem kontrol", "pid controller", "actuator", "aktuator",
        "process control", "kontrol proses", "autonomous system", "sistem otonom",
    ],

    # --- Software, Data, and Information Systems ---
    "software-engineering": [
        "software engineering", "rekayasa perangkat lunak", "software testing",
        "software architecture", "software quality", "agile", "scrum",
        "requirement engineering", "rekayasa kebutuhan",
        "software development life cycle", "sdlc", "microservices",
        "design pattern", "software maintenance", "unit testing",
        "code review", "version control", "devops", "continuous integration",
        "api design", "software metrics",
    ],
    "website": [
        "web application", "aplikasi web", "website development",
        "sistem informasi berbasis web", "web-based information system",
        "e-commerce", "content management system", "cms", "web development",
        "pengembangan website", "responsive web design", "frontend development",
        "backend development", "web service", "restful api",
    ],
    "mobile-app": [
        "mobile application", "aplikasi mobile", "android application",
        "aplikasi android", "ios application", "mobile app development",
        "cross-platform mobile", "flutter", "react native", "mobile computing",
        "aplikasi bergerak", "hybrid mobile app",
    ],
    "database": [
        "database", "basis data", "database design", "sql", "nosql",
        "data warehouse", "database management system", "query optimization",
        "relational database", "database terdistribusi", "distributed database",
        "data modeling", "pemodelan data", "database performance",
        "mongodb", "postgresql", "mysql", "data lake",
    ],

    # --- Human-Centered Computing and Education ---
    "human-computer-interaction": [
        "human-computer interaction", "human computer interaction", "hci",
        "interaksi manusia komputer", "usability testing", "usability",
        "usability evaluation", "evaluasi usabilitas", "interaction design",
        "desain interaksi", "accessibility", "aksesibilitas",
        "user-centered design", "desain berpusat pengguna",
    ],
    "ui": [
        "user interface", "antarmuka pengguna", "interface design",
        "desain antarmuka", "ui design", "visual design", "desain visual",
        "wireframe", "prototyping", "prototipe antarmuka",
    ],
    "ux": [
        "user experience", "pengalaman pengguna", "ux design", "ux research",
        "user research", "riset pengguna", "usability testing",
        "user experience questionnaire", "system usability scale",
        "design thinking", "user journey", "customer experience",
    ],
    "e-learning": [
        "e-learning", "electronic learning", "pembelajaran daring",
        "pembelajaran online", "learning management system", "lms",
        "media pembelajaran", "distance learning", "blended learning",
        "online learning", "computer-based learning", "gamifikasi",
        "gamification", "educational technology", "teknologi pendidikan",
        "massive open online course", "mooc", "adaptive learning",
    ],
    "immersive-technology": [
        "virtual reality", "vr", "augmented reality", "ar",
        "mixed reality", "immersive technology", "realitas virtual",
        "realitas tertambah", "realitas campuran", "metaverse",
        "extended reality", "xr", "3d simulation", "simulasi 3d",
        "head-mounted display", "digital twin",
    ],
}
