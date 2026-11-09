"""Conservative US location classification from source-provided location text."""
from __future__ import annotations

import ast
import json
import re
import subprocess
import unicodedata
from collections import defaultdict
from functools import lru_cache

from .store import ROOT

STATE_NAMES = "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia".split("|")
STATE_CODES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
STATES = dict(zip([n.casefold() for n in STATE_NAMES], STATE_CODES))
STATES.update({code.casefold(): code for code in STATE_CODES})


def fold(value):
    s = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def city_text(value):
    s = fold(value)
    s = re.sub(r"\b(?:remote|hybrid|onsite|on site|office|headquarters|hq|greater|metropolitan|metro|area|based|in|at)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    aliases = {"nyc": "new york city", "new york": "new york city", "sf": "san francisco", "san francisco bay": "san francisco", "sf bay": "san francisco", "bay": "san francisco", "washington d c": "washington", "washington dc": "washington"}
    return aliases.get(s, s)


MAJOR_US = {
    "new york", "new york city", "nyc", "san francisco", "san francisco bay area", "sf bay area", "silicon valley",
    "los angeles", "seattle", "boston", "austin", "chicago", "denver", "atlanta", "san diego", "houston",
    "dallas", "miami", "baltimore", "philadelphia", "pittsburgh", "minneapolis", "las vegas", "raleigh",
    "salt lake city", "palo alto", "washington dc", "washington d c", "south san francisco",
}
FOREIGN_MAJOR = {
    "london", "paris", "berlin", "toronto", "vancouver", "singapore", "bengaluru", "bangalore", "mumbai",
    "delhi", "new delhi", "tokyo", "sydney", "melbourne", "amsterdam", "dublin", "cambridge", "munich",
    "madrid", "barcelona", "seoul", "taipei", "hong kong", "shanghai", "beijing", "warsaw", "krakow",
    "prague", "lisbon", "porto", "zurich", "geneva", "dubai", "tel aviv", "tbilisi", "montreal", "ottawa",
    "buenos aires", "mexico city", "sao paulo", "bogota", "manila", "jakarta", "kuala lumpur", "bangkok",
    "ho chi minh city", "hanoi", "cape town", "johannesburg", "cairo", "riyadh", "istanbul", "perth",
}
US_LABEL = re.compile(r"\b(?:united states(?: of america)?|usa|u[.\s]*s(?:[.\s]*a)?\.?)\b", re.I)
GLOBAL = re.compile(r"\b(?:worldwide|world wide|anywhere|global|north america|south america|latin america|central america|americas|latam|emea|apac|europe|africa|asia|oceania)\b", re.I)
NON_US = re.compile(r"\b(?:non[- ]?u\.?s\.?|outside (?:the )?(?:u\.?s\.?|united states)|(?:excluding|except) (?:the )?(?:u\.?s\.?|united states))\b", re.I)
SPLIT = re.compile(r"\s*(?:[;|/•\n]|\s+(?:or|and|&)\s+)\s*", re.I)
NEUTRAL = {"", "remote", "hybrid", "on site", "onsite", "office", "in office", "hq", "work from home"}
FOREIGN_CODES = {"GB", "UK", "AU", "NZ", "BR", "CN", "JP", "KR", "SG", "MX", "FR", "ES", "IT", "NL", "PL", "IE", "CH", "AE", "ZA", "PH", "VN", "TH", "HK", "TW", "PT", "CZ", "RO", "SE", "DK", "NO", "FI", "BE", "NZ", "AR"}
FOREIGN_REGIONS = {"ontario", "quebec", "british columbia", "alberta", "manitoba", "saskatchewan", "nova scotia", "new brunswick", "prince edward island", "newfoundland and labrador", "yukon", "northwest territories", "nunavut", "western australia", "new south wales", "queensland", "tasmania", "south australia", "northern territory"}


class USLocations:
    def __init__(self, extra_locations=()):
        data = json.loads((ROOT / "sources/job-board-aggregator/data/locations.json").read_text())
        schema, rows = data["schema"], data["data"]
        ci, ai, co = (schema.index(k) for k in ("city", "admin", "country"))
        self.countries = defaultdict(set)
        self.us_pairs = set()
        for row in rows:
            name, country = fold(row[ci]), row[co]
            self.countries[name].add(country)
            if country == "US":
                self.us_pairs.add((name, str(row[ai]).upper()))
        self.us_pairs.update({("new york city", "NY"), ("new york", "NY"), ("washington", "DC")})

        # Built-in ICU region names cover countries missing from the reference aliases.
        codes = sorted({row[co] for row in rows})
        self.foreign_codes = (set(codes) | FOREIGN_CODES | {"ON", "BC", "QC", "AB", "MB", "SK", "NS", "NB", "PE", "NU", "NT", "YT"}) - set(STATE_CODES) - {"US"}
        self.foreign_code = re.compile(r"(?<![A-Za-z])(?:" + "|".join(sorted(self.foreign_codes)) + r")(?![A-Za-z])")
        self.safe_state_codes = set(STATE_CODES) - set(codes) - {"WA"}
        source = "const fs=require('node:fs');const d=new Intl.DisplayNames(['en'],{type:'region'});process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(c=>[d.of(c),c])));"
        names = json.loads(subprocess.check_output(["node", "-e", source], input=json.dumps(codes), text=True))
        aliases = {}
        tree = ast.parse((ROOT / "sources/job-board-aggregator/scripts/geolocation.py").read_text())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "COUNTRY_ALIASES" for t in node.targets):
                aliases = ast.literal_eval(node.value)
        foreign = {fold(name) for name, code in names if code != "US"}
        foreign.update(fold(name) for name, code in aliases.items() if code != "US" and len(fold(name)) >= 3)
        foreign.discard("georgia")  # Georgia needs city/state or country context.
        self.foreign_country = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in sorted(foreign, key=len, reverse=True)) + r")\b")
        state_pattern = "|".join(re.escape(n) for n in sorted(STATE_NAMES, key=len, reverse=True))
        state_token = rf"(?:(?i:{state_pattern})|{'|'.join(STATE_CODES)})"
        self.pair = re.compile(rf"(?P<city>[^,;|/•\n]{{1,120}}),\s*(?P<state>{state_token})(?=$|[\s,;|/•()])")
        self.space_pair = re.compile(rf"^(?P<city>.+?)\s+(?P<state>{state_token})(?:\s+\d{{5}}(?:-\d{{4}})?)?\s*$")
        self.full_state = re.compile(r"\b(?:" + "|".join(re.escape(n.casefold()) for n in STATE_NAMES if n != "Georgia") + r")\b")
        for location in extra_locations:
            if not US_LABEL.search(location) or GLOBAL.search(location) or NON_US.search(location):
                continue
            if self.foreign_country.search(fold(location).replace("new mexico", "usstate")):
                continue
            for match in self.pair.finditer(location):
                name, code = city_text(match["city"]), STATES.get(match["state"].casefold())
                if name and code:
                    self.us_pairs.add((name, code))
                    self.countries[name].add("US")

    def valid_pair(self, city, state):
        code = STATES.get(state.casefold())
        name = city_text(city)
        if code in self.safe_state_codes:
            return True
        # Addresses and office labels may precede the city name.
        words = name.split()
        return any((" ".join(words[i:]), code) in self.us_pairs for i in range(max(0, len(words)-6), len(words)))

    def segment(self, value):
        normalized = fold(value)
        if normalized in NEUTRAL:
            return "neutral", "arrangement_only"
        if NON_US.search(value) or GLOBAL.search(value):
            return "excluded", "non_us_or_broad_region"
        # "Mexico" inside "New Mexico" is a US state name, not another country.
        foreign_text = normalized.replace("new mexico", "usstate")
        if self.foreign_country.search(foreign_text):
            return "excluded", "non_us_country"

        valid = []
        for match in self.pair.finditer(value):
            if self.valid_pair(match["city"], match["state"]):
                valid.append(match.span())
        space = self.space_pair.match(value)
        if space and self.valid_pair(space["city"], space["state"]):
            valid.append(space.span())
        remainder = value
        for start, end in sorted(valid, reverse=True):
            remainder = remainder[:start] + " " + remainder[end:]
        for token in re.split(r"[,()]", remainder):
            city = city_text(token)
            if city in FOREIGN_MAJOR or city in FOREIGN_REGIONS:
                return "excluded", "foreign_or_ambiguous_city"
        # Unambiguous foreign ISO codes must not become US state/city evidence.
        if self.foreign_code.search(remainder) or any(city_text(token).upper() in self.foreign_codes for token in re.split(r"[,()]", remainder)):
            return "excluded", "non_us_country_code"
        if US_LABEL.search(value) or US_LABEL.search(normalized):
            if re.search(r"\b(?:timezones?|time zones?)\b", normalized):
                return "excluded", "timezone_is_not_country"
            return "US", "us_country_label"
        if valid:
            # Every other location token must also be understood. A valid US
            # city/state followed by an unresolved city is not assumed US-only.
            remaining = city_text(remainder.strip(" ,()"))
            if remaining and remaining not in NEUTRAL and remaining not in MAJOR_US and not re.fullmatch(r"\d{5}(?: \d{4})?", remaining):
                return "excluded", "unresolved_additional_location"
            return "US", "us_city_and_state"
        if self.full_state.search(normalized):
            return "US", "us_state_name"
        city = city_text(value)
        if normalized in MAJOR_US or city in MAJOR_US:
            return "US", "recognised_us_city"
        if city not in FOREIGN_REGIONS and self.countries.get(city) == {"US"}:
            return "US", "unambiguous_us_city"
        return "excluded", "location_not_established_as_us"

    @lru_cache(maxsize=150000)
    def match(self, location):
        if not location or not location.strip():
            return False, "missing_location"
        if NON_US.search(location) or GLOBAL.search(location):
            return False, "non_us_or_broad_region"
        parts = [self.segment(p) for p in SPLIT.split(location) if p.strip()]
        if not parts or any(result == "excluded" for result, _ in parts):
            return False, next((why for result, why in parts if result == "excluded"), "missing_location")
        matches = [why for result, why in parts if result == "US"]
        return (True, "; ".join(sorted(set(matches)))) if matches else (False, "location_not_established_as_us")
