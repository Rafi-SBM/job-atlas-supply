"""Primary role families for organizing job listings without changing titles."""
import re


def rule(name, pattern):
    return name, re.compile(pattern, re.I)


RULES = [
    rule("General Applications", r"general (?:application|interest)|open application|future opportunit|talent (?:pool|community)|expression of interest|join (?:our|the) team|unsolicited application"),
    rule("Executive Leadership", r"^(?:\([^)]{1,30}\)\s*)?(?:(?:interim|fractional|founding|group|global|regional|deputy|acting|part.time)\s+)?(?:chief .{0,35}officer|chief executive|(?:ceo|cfo|coo|cto|cmo|chro)\b|president\b|(?:co[- ]?)?founder\b)"),
    rule("Veterinary and Animal Care", r"veterinar|\bvet(?:erinary)? (?:tech|assistant)|animal (?:care|health|technician)|dog (?:trainer|groomer)|pet groom"),
    rule("Healthcare and Nursing", r"\bnurs(?:e|ing)\b|\b(?:rn|lpn|lvn|cna|pmhnp)\b|physician|medical (?:assistant|director|doctor|scribe|office)|patient (?:care|access|service)|dent(?:ist|al)|pharmac|radiolog|sonograph|optometr|surg(?:eon|ical)|anesthes|caregiver|home health|respiratory|clinical (?:assistant|director|specialist|manager|coordinator)|\bemt\b|paramedic|phlebotom"),
    rule("Therapy and Behavioral Health", r"therap(?:ist|y)|psych(?:iatrist|ologist|otherap|ology)|behavior(?:al)?|mental health|\b(?:rbt|bcba|aba|lcsw|lmft|lpc|slp)\b|speech.language|social worker|counselor|rehabilitation"),
    rule("Fitness and Wellness", r"personal trainer|fitness|wellness|athletic|yoga|pilates|strength and conditioning|exercise|massage|cosmetolog|hair (?:stylist|color|colorist)|hairstylist|esthetician|aesthetician|barber|nutrition|dietitian|sports (?:coach|performance)"),
    rule("Legal and Compliance", r"attorney|lawyer|paralegal|legal|\bcounsel\b|litigation|compliance|regulatory|privacy (?:officer|counsel)|legal process|government affairs|policy (?:advisor|analyst|manager)"),
    rule("HR and Recruiting", r"recruit|human resources|\bhr\b|people (?:operations|partner|business|experience|team)|talent (?:acquisition|partner|development)|compensation|benefits (?:specialist|manager|analyst)|employee relations|learning and development|workforce planning"),
    rule("Finance and Accounting", r"accountant|accounting|\bfinance\b|financial|\bcontroller\b|bookkeep|payroll|treasury|\btax\b|auditor|\baudit\b|accounts (?:payable|receivable)|\bfp&a\b|investment|banker|banking|underwriter|mortgage|loan (?:officer|processor)|credit (?:analyst|manager)|portfolio manager|wealth (?:advisor|management)|actuar"),
    rule("Real Estate and Property", r"real estate|realtor|leasing|property (?:manager|management|administrator|accountant)|community (?:manager|director)|land acquisition|title (?:officer|examiner)|escrow|apartment"),
    rule("Drivers and Transportation", r"\bdriver\b|\bdriving\b|\bcdl\b|truck(?:er|ing)|delivery (?:rider|partner|courier)|\bcourier\b|\bpilot\b|flight attendant|transportation (?:operator|specialist)|bus operator"),
    rule("Hospitality and Food Service", r"restaurant|\bchef\b|\bcook\b|kitchen|food (?:service|prep|production)|\bbarista\b|bartender|\bserver\b(?!\s*(?:engineer|developer|infrastructure))|host(?:ess)?\b|hospitality|hotel|housekeep|concierge|front (?:desk|office) (?:agent|associate)|cookie crew|catering|baker|dishwasher"),
    rule("Retail and Store Management", r"sales associate|retail|\bstore\b|key holder|cashier|merchandis|shop (?:manager|associate)|wireless sales|boutique|brand ambassador|beauty advisor|visual (?:associate|specialist)"),
    rule("Sales and Business Development", r"\bsales\b|account (?:executive|manager|director)|business develop|sales develop|\b(?:sdr|bdr)\b|solutions? (?:engineer|consultant|architect)|presales|pre[- ]sales|commercial (?:director|manager|account)|revenue (?:operations|enablement)|partnership|channel (?:manager|director)|growth (?:account|sales)|customer acquisition"),
    rule("Customer Success and Support", r"customer (?:success|support|service|experience|care)|client (?:success|service|support)|technical (?:support|account)|support (?:engineer|specialist|representative|agent)|contact center|call cent(?:er|re)|implementation (?:manager|specialist|consultant)|onboarding (?:specialist|manager)|user operations"),
    rule("Marketing and Communications", r"marketing|\bseo\b|\bsem\b|communications|public relations|social media|copywriter|content (?:writer|creator|strategist|marketer)|demand generat|\bbrand\b|campaign|paid (?:media|search)|advertis|email (?:specialist|manager)|community (?:lead|engagement)"),
    rule("Administrative and Data Entry", r"data entry|executive assistant|administrative|office (?:manager|assistant|administrator|coordinator)|receptionist|\bclerk\b|personal assistant|virtual assistant|scheduler|appointment setter|front desk|secretary|document (?:control|specialist)"),
    rule("Education and Training", r"\bteach(?:er|ing)\b|professor|\btutor\b|instructor|curriculum|instructional|educator|education|school (?:counselor|principal|administrator)|academic|student (?:advisor|success)|\blibrarian\b|camp (?:counselor|leader|director)|\btrainer\b"),
    rule("Data and AI", r"data (?:engineer|scientist|analyst|architect|science|analytics|model|contributor|collector|annotat|label)|machine learning|\bml (?:engineer|research|scientist)|\bai(?:/ml)?\b|artificial intelligence|\bllm\b|\bnlp\b|computer vision|business intelligence|\banalytics\b|statistician|quantitative (?:analyst|research)|quant (?:research|developer)|database (?:engineer|developer)|\bbi (?:engineer|analyst|developer)"),
    rule("Design and Creative", r"\bdesign(?:er)?\b|\bux\b|\bui\b|user experience|user research|graphic|creative|art director|illustrat|animat|videograph|photograph|video editor|motion (?:artist|graphics)|game artist|\b3d artist"),
    rule("Projects and Programs", r"project (?:manager|coordinator|director|management|engineer)|program (?:manager|director|coordinator|management)|programme|\bpmo\b|scrum master|agile coach|delivery manager|engagement manager"),
    rule("Product Management", r"product (?:manager|management|owner|lead|director|operations)|director.{0,15}product\b|head of product|vp.{0,10}product\b|product strategy"),
    rule("IT Cloud and Cybersecurity", r"\b(?:devops|devsecops|sre)\b|site reliability|cloud (?:engineer|architect|administrator|operations)|\bit (?:support|specialist|manager|director|administrator|technician|engineer)|information technology|help.?desk|desktop support|system[sc]? administrator|network (?:engineer|administrator|architect)|infrastructure (?:engineer|architect)|cyber|infosec|information security|security (?:engineer|analyst|architect)|penetration|\bsoc analyst|endpoint|database administrator"),
    rule("Software Engineering", r"software|\bdeveloper\b|front.?end|back.?end|full.?stack|web (?:engineer|development)|mobile (?:engineer|development)|\b(?:ios|android) engineer|application[sc]? (?:engineer|developer|architect)|platform engineer|member of technical staff|engineering manager|qa engineer|software test|test automation|\bsdet\b|software architect|forward deployed engineer"),
    rule("Manufacturing and Quality", r"manufactur|production (?:operator|technician|supervisor|manager)|quality (?:engineer|inspector|technician|assurance|control|manager)|\bqc\b|assembly|assembler|fabricat|machinist|\bcnc\b|industrial engineer|process engineer|tool(?:ing|maker)|packag(?:ing|er)|plant (?:manager|operator)|test technician"),
    rule("Skilled Trades and Maintenance", r"maintenance|mechanic\b|hvac|electrician|plumber|carpenter|welder|field (?:service |)technician|service technician|repair|equipment (?:technician|operator)|facilities|custodian|janitor|landscap|groundskeep|installer|install(?:ation)? technician|handyman|pest control|cleaner"),
    rule("Supply Chain and Logistics", r"supply chain|logistics|warehouse|procurement|purchas|inventory|shipping|receiving|fulfillment|\bforklift\b|material (?:handler|planner)|distribution|freight|demand planner|sourcing (?:manager|specialist)|buyer|dispatch"),
    rule("Physical Security and Safety", r"security (?:guard|officer|supervisor)|physical security|public safety|safety (?:officer|specialist|manager|coordinator)|\behs\b|\bhse\b|environmental health|loss prevention|police|firefighter|fire (?:marshal|inspector)|security clearance investigator"),
    rule("Science and Research", r"scientist|laboratory|\blab (?:tech|assistant|manager|scientist)|research (?:associate|assistant|fellow|scientist)|biolog|biochem|chemist|clinical research|clinical trial|biostatistic|microbiolog|geolog|physicist|postdoc"),
    rule("Hardware and Engineering", r"\bengineer\b|engineering|hardware|electrical|electronic|firmware|embedded|aerospace|mechanical|avionics|robotic|\barchitect\b|civil|structural|construction|superintendent|surveyor|estimator|draft(?:er|ing)|\bcad\b|\bbim\b|\bfpga\b|\basic\b|\brf\b"),
    rule("Business Operations", r"operations|business (?:analyst|operations|manager)|chief of staff|general manager|assistant manager|strategy|strategic|consultant|consulting|management|\bmanager\b|\bdirector\b|coordinator|supervisor|team lead|shift (?:lead|leader)|leadership|associate"),
]

# These last-resort title labels are generic; a meaningful department takes precedence.
GENERIC_GROUPS = {"Business Operations", "Hardware and Engineering"}


def classify_role(title, department=""):
    # Pay rates such as "$24.89/HR" describe hourly pay, not human resources.
    text = re.sub(r"(?<=\d)\s*/\s*hr\b", " per hour", title or "", flags=re.I)
    text = re.sub(r"[_–—/]+", " ", text)
    # Resolve explicit functions before incidental executive or industry words.
    specific = [
        ("Administrative and Data Entry", r"executive assistant|assistant to (?:the )?(?:ceo|cfo|coo|cto|chief)"),
        ("Business Operations", r"chief of staff|founder.s office|\b(?:ceo|cfo|coo|cto) intern\b"),
        ("Sales and Business Development", r"account (?:executive|cto)\b"),
        ("IT Cloud and Cybersecurity", r"information systems? security|information assurance|\bisso\b"),
        ("Manufacturing and Quality", r"product quality|process engineer"),
        ("Science and Research", r"clinical research|clinical trial|research technician"),
        ("Skilled Trades and Maintenance", r"concrete finisher|flatwork"),
    ]
    for name, pattern in specific:
        if re.search(pattern, text, re.I):
            return name, "job_title"
    candidate = None
    for name, pattern in RULES:
        if pattern.search(text):
            if name == "Hospitality and Food Service" and re.search(r"software|engineer|developer|infrastructure|server.side|serverless", text, re.I) and not re.search(r"restaurant|kitchen|hotel|food service", text, re.I):
                continue
            if name == "Data and AI" and re.search(r"(?:product|project|program) manager|product designer|ux designer", text, re.I):
                continue
            if name == "Design and Creative":
                if re.search(r"(?:project|program) manager", text, re.I):
                    return "Projects and Programs", "job_title"
                if re.search(r"software|frontend|front.end|backend|back.end|developer", text, re.I):
                    return "Software Engineering", "job_title"
                if re.search(r"engineer|engineering|\bcad\b|\bbim\b|mission design", text, re.I):
                    return "Hardware and Engineering", "job_title"
            if name not in GENERIC_GROUPS:
                return name, "job_title"
            candidate = name
            break
    dept = re.sub(r"[_–—/]+", " ", department or "")
    if dept:
        for name, pattern in RULES:
            if name not in {"General Applications", "Executive Leadership", "Business Operations"} and pattern.search(dept):
                return name, "department"
    if candidate:
        return candidate, "job_title"
    for name, pattern in ADDITIONAL_RULES:
        if pattern.search(text):
            return name, "job_title"
    return "Other Roles", "unclassified"


ADDITIONAL_RULES = [
    rule("Healthcare and Nursing", r"health|personal care|direct support professional|\bdsp\b|endodont|gynecolog|endocrinolog|podiatr|cardiolog|dermatolog|ophthalm|neurolog|orthodont|orthoped|urolog|pediatric|otolaryng|oncolog|gastroenterolog|nephrolog|rheumatolog|\bhospit|care assistant"),
    rule("Therapy and Behavioral Health", r"child development|autism|early intervention|child life|crisis (?:worker|specialist)|support counselor"),
    rule("HR and Recruiting", r"\btalent\b|people partner|organizational development"),
    rule("Finance and Accounting", r"valuations?|risk analyst|revenue analyst|cost analyst|billing|insurance|claims|adjuster|fund (?:administrator|account)|collections|accounting"),
    rule("Hospitality and Food Service", r"culinary|food and beverage|\bwaiter\b|waitress|waitstaff|banquet|sommelier|\bporter\b|\bmaid\b"),
    rule("Retail and Store Management", r"style advisor|key lead|dispensary|budtender|showroom|salesperson|shopkeeper|grocery|stocker"),
    rule("Real Estate and Property", r"home (?:buying|buyer|inspector|inspection|advisor)|property|appraiser"),
    rule("Legal and Compliance", r"court|contract specialist|docket|litigation|regulatory|litigator"),
    rule("Education and Training", r"paraprofessional|substitute|childcare|daycare|day care|recreation|teaching|faculty|dean|principal|training"),
    rule("Administrative and Data Entry", r"executive business partner|clerical|records specialist|administration|typist|transcription|appointment"),
    rule("IT Cloud and Cybersecurity", r"data cent(?:er|re)|network exploitation|\bnetwork\b|cryptolog|computer|\bit\b|technical support"),
    rule("Physical Security and Safety", r"\bsecurity\b|\bcctv\b|surveillance|fire alarm|environmental specialist"),
    rule("Skilled Trades and Maintenance", r"technician|\btech\b|plumb|contractor|laborer|labourer|foreman|detailer|lot attendant|yard|mechanic|repair|electric|facilit|wastewater|water treatment|building (?:inspector|inspections)|construction worker"),
    rule("Manufacturing and Quality", r"operator|production|\bquality\b|processing|inspection|inspector"),
    rule("Sales and Business Development", r"canvass|account specialist|\brepresentative\b|business development|enrollment|solicitor"),
    rule("Data and AI", r"\banalyst\b|\banalysis\b|\bdata\b"),
    rule("Business Operations", r"strategist|\blead\b|\bleader\b|specialist|\bofficer\b|business partner|administrator|partner|ownership|franchise"),
]
