import json
import unittest
from scraper.availability import evidence, expired, non_vacancy, target


class AvailabilityTests(unittest.TestCase):
    def row(self, platform="greenhouse"):
        return {"platform": platform, "board": "sample", "job_id": "42", "title": "Engineer",
                "url": "https://jobs.example.com/sample/42", "apply_url": "https://jobs.example.com/sample/42/apply"}

    def test_http_success_without_application_evidence_is_not_open(self):
        row = self.row("lever")
        result = evidence(row, "<html><h2>Job no longer available</h2></html>", row["apply_url"])
        self.assertEqual(result[0], "unconfirmed")

    def test_specific_greenhouse_application_schema(self):
        data = {"id": 42, "internal_job_id": 7, "title": "Software Engineer", "location": {"name": "New York, NY"},
                "questions": [{"fields": [{"name": n}]} for n in ["first_name", "last_name", "email"]]}
        self.assertEqual(evidence(self.row(), json.dumps(data), "https://example.com")[0], "open")
        data["internal_job_id"] = None
        self.assertEqual(evidence(self.row(), json.dumps(data), "https://example.com")[0], "excluded_general")
        data["internal_job_id"] = 7
        data["application_deadline"] = "2020-01-01"
        self.assertEqual(evidence(self.row(), json.dumps(data), "https://example.com")[0], "closed")

    def test_job_identity_must_match(self):
        data = {"id": 100}
        self.assertEqual(evidence(self.row(), json.dumps(data), "https://example.com")[0], "unconfirmed")

    def test_form_is_not_enough_for_general_application(self):
        page = '<h2>General Application</h2><div class="location">New York, NY</div><form id="application-form"><input name="name"><input name="email"></form>'
        self.assertEqual(evidence(self.row("lever"), page, "https://example.com/42/apply")[0], "excluded_general")
        page = page.replace("General Application", "Software Engineer")
        self.assertEqual(evidence(self.row("lever"), page, "https://example.com/42/apply")[0], "open")

    def test_workday_explicit_can_apply(self):
        row = self.row("workday")
        job = {"jobReqId": "42", "title": "Engineer", "location": "Austin", "country": {"descriptor": "United States"}, "canApply": False, "posted": True}
        self.assertEqual(evidence(row, json.dumps({"jobPostingInfo": job}), row["url"])[0], "closed")
        job["canApply"] = True
        self.assertEqual(evidence(row, json.dumps({"jobPostingInfo": job}), row["url"])[0], "open")

    def test_generic_titles_and_deadlines(self):
        for title in ["General Employment Application", "Join our talent network", "Future Opportunities", "Evergreen Nurse", "Demo Job",
                      '"Looking for Another Job Position Not Shown Here?" (in-office only)',
                      "Don't See Your Role?", "General Resume Submission", "Submit Your Resume!",
                      "Hiring Event", "All Positions", "Spontaneous Application", "Apply Now",
                      "General Applicants", "General Consideration", "Resume Drop", "Career Opportunities",
                      "Future Territory Account Manager", "General Prism Job Application",
                      "(Pipeline) Structural Analyst, Space Emerging Talent", "Test", "Expressions of Interest",
                      "Teacher -Candidate Pool 2026-2027 School Year"]:
            self.assertTrue(non_vacancy(title), title)
        for title in ["QA Test Engineer", "Recruiter, Talent Acquisition", "Registered Nurse", "2027 Summer Internship",
                      "General Software Engineer", "General Liability Associate Attorney", "CV/ML Platform Engineer",
                      "Director, Business Development (Future Mobility)", "Pipeline Engineer", "Pipeline Operator"]:
            self.assertFalse(non_vacancy(title), title)
        self.assertTrue(expired("2020-01-01"))
        self.assertTrue(expired("unreadable deadline"))
        self.assertFalse(expired(None))
        self.assertFalse(expired("2099-01-01"))

    def test_candidate_application_limits_do_not_mean_the_role_is_closed(self):
        row = self.row("ashby")
        posting = {"id": "42", "title": "Software Engineer", "isListed": True,
                   "locationName": "New York, NY", "applicationDeadline": None,
                   "applicationLimitCalloutHtml": "Candidates may apply for open roles up to 3 times in 60 days."}
        page = "window.__appData = " + json.dumps({"posting": posting}) + ";"
        self.assertEqual(evidence(row, page, "https://jobs.ashbyhq.com/sample/42/application")[0], "open")
        posting["applicationLimitCalloutHtml"] = "Applications are closed."
        page = "window.__appData = " + json.dumps({"posting": posting}) + ";"
        self.assertEqual(evidence(row, page, "https://jobs.ashbyhq.com/sample/42/application")[0], "closed")


if __name__ == "__main__":
    unittest.main()
