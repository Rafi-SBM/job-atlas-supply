import unittest
from scraper.role_groups import classify_role


class RoleGroupTests(unittest.TestCase):
    def test_function_specific_titles(self):
        cases = {
            "Senior Software Engineer": "Software Engineering",
            "Software Sales Engineer": "Sales and Business Development",
            "Senior Data Engineer": "Data and AI",
            "Product Marketing Manager": "Marketing and Communications",
            "Product Manager": "Product Management",
            "Technical Program Manager": "Projects and Programs",
            "Customer Success Engineer": "Customer Success and Support",
            "Registered Nurse": "Healthcare and Nursing",
            "Psychiatric Mental Health Nurse Practitioner": "Healthcare and Nursing",
            "Registered Behavior Technician (RBT)": "Therapy and Behavioral Health",
            "Personal Trainer": "Fitness and Wellness",
            "Work at Home Data Entry Agent": "Administrative and Data Entry",
            "Retail Sales Associate": "Retail and Store Management",
            "Veterinary Technician": "Veterinary and Animal Care",
            "Heavy Equipment Field Technician (Mechanic)": "Skilled Trades and Maintenance",
            "Data collector / Driver": "Drivers and Transportation",
            "Senior Electrical Engineer": "Hardware and Engineering",
            "General Application": "General Applications",
            "Senior Software Engineer - Server": "Software Engineering",
            "Electrical Design Engineer": "Hardware and Engineering",
            "Frontend Engineer (UI)": "Software Engineering",
            "Product Manager, AI": "Product Management",
            "Child Autism Specialist": "Therapy and Behavioral Health",
            "Health Information Specialist I": "Healthcare and Nursing",
            "$24.89/HR – UNION NIGHT GROCERY STOCKER": "Retail and Store Management",
            "Account Executive - CFO Solutions": "Sales and Business Development",
            "Founder’s Office | Chief of Staff to the CEO": "Business Operations",
            "Executive Assistant to the CEO": "Administrative and Data Entry",
            "Information System Security Officer (ISSO) III": "IT Cloud and Cybersecurity",
            "(Senior) Director, Product Quality": "Manufacturing and Quality",
            "Member of Technical Staff / Director, Process Engineering": "Manufacturing and Quality",
            "(Contract) Research Technician, Pre-clinical Pharmacology": "Science and Research",
            "(FLATWORK) Concrete Finisher": "Skilled Trades and Maintenance",
            "Administrative Assistant, Office of the CEO": "Administrative and Data Entry",
            "AI Associate, Office of the CEO": "Data and AI",
            "Chief Financial Officer": "Executive Leadership",
            "Fractional CTO": "Executive Leadership",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(classify_role(title)[0], expected)

    def test_department_fallback_and_unknown(self):
        self.assertEqual(classify_role("Assistant Manager", "Retail Sales")[0], "Retail and Store Management")
        self.assertEqual(classify_role("Specialist", "Software Engineering")[0], "Software Engineering")
        self.assertEqual(classify_role("Unspecified opportunity")[0], "Other Roles")


if __name__ == "__main__":
    unittest.main()
