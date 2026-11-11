"""Services and background jobs: the AI -> Logic -> Data pipeline, recommendations,
the recommendation cache and the threaded job queue."""
import threading
import time

import pytest

from conftest import (PROTEIN_MIN_15, SUGAR_MAX_10, Replies, analysis_answer, make_ai, product,
                      profile)
from nutrilenz.ai.label_image import LabelImage
from nutrilenz.data.seeder import DemoDataSeeder
from nutrilenz.domain.flag import Flag
from nutrilenz.domain.nutrients import Nutrient
from nutrilenz.domain.recommendation_focus import RecommendationFocus
from nutrilenz.domain.recommendation_options import RecommendationOptions
from nutrilenz.errors.ai_error import AIError
from nutrilenz.errors.data_error import DataError
from nutrilenz.services.analysis_service import AnalysisService
from nutrilenz.services.job_manager import JobManager
from nutrilenz.services.job_observer import JobObserver
from nutrilenz.services.job_status import JobStatus
from nutrilenz.services.recommendation_service import RecommendationService


def wait_for(job, seconds=5):
    end = time.time() + seconds
    while not job.finished and time.time() < end:
        time.sleep(0.01)
    assert job.finished


class TestAnalysisService:
    def test_pipeline_saves_a_full_record(self, data, logic):
        ai, _, _ = make_ai(Replies.gemini(analysis_answer()))
        user = data.register("jane", "secret123", [SUGAR_MAX_10], [])
        outcome = AnalysisService(ai, logic, data).analyse(user, product())
        assert outcome.saved
        saved = data.history(user.user_id)[0]
        assert saved.flag_names() == ["GOAL_MISMATCH", "CLAIM_REVIEW"]
        assert saved.provider == "gemini"

    def test_ai_failure_saves_nothing(self, data, logic):
        ai, _, _ = make_ai(AIError("CONFIGURATION_ERROR"), groq_replies=[AIError("CONFIGURATION_ERROR")])
        user = data.register("jane", "secret123", [SUGAR_MAX_10], [])
        with pytest.raises(AIError):
            AnalysisService(ai, logic, data).analyse(user, product())
        assert data.history(user.user_id) == []

    def test_save_failure_still_returns_result(self, data, logic):
        ai, _, _ = make_ai(Replies.gemini(analysis_answer()))
        user = data.register("jane", "secret123", [SUGAR_MAX_10], [])
        data.delete_account(user.user_id)                  # saving will now fail
        outcome = AnalysisService(ai, logic, data).analyse(user, product())
        assert not outcome.saved and outcome.error_code == "USER_NOT_FOUND"
        assert outcome.analysis.has_flag(Flag.GOAL_MISMATCH)

    def test_unreadable_photo(self, data, logic):
        reading = {"readable": False, "product_name": None, "brand": None, "category": None,
                   "nutrition": {key: None for key in Nutrient.keys()}, "ingredient_text": None,
                   "marketing_claim": None, "notes": "Not a food label"}
        ai, _, _ = make_ai(Replies.gemini(reading))
        with pytest.raises(AIError) as error:
            AnalysisService(ai, logic, data).read_label(LabelImage(b"img", "image/png"))
        assert error.value.code == "UNREADABLE_IMAGE"


class TestRecommendationService:
    def advice(self, product_id):
        return {"picks": [{"product_id": product_id, "reason": "Most protein"}], "tips": ["Eat fish"],
                "suggested_products": [{"name": "Ayam Brand Tuna in Water", "brand": "Ayam Brand",
                                        "reason": "High protein"}]}

    def test_shortlist_explained_and_cached(self, data, logic):
        DemoDataSeeder(data, logic).seed_if_empty()
        sam = data.authenticate("sam", "sam12345")
        options = RecommendationOptions([RecommendationFocus.HIGHEST_PROTEIN])
        top = logic.rank(data.catalogue(), sam.profile, options)[0].product
        ai, gemini, _ = make_ai(Replies.gemini(self.advice(top.product_id)))
        service = RecommendationService(ai, logic, data)

        first = service.recommend(sam, options)
        assert [item.product.name for item in first.items()] == [top.name]
        assert first.reason_for(top.product_id) == "Most protein"
        assert first.suggested_products[0].brand == "Ayam Brand"
        assert all("peanuts" not in item.product.ingredient_text.lower() for item in first.items())

        assert service.recommend(sam, options) is first          # cached: no second AI call
        assert gemini.calls == 1

    def test_changing_goals_skips_the_cache(self, data, logic):
        DemoDataSeeder(data, logic).seed_if_empty()
        sam = data.authenticate("sam", "sam12345")
        options = RecommendationOptions()
        before = logic.rank(data.catalogue(), sam.profile, options)[0].product.product_id
        after = logic.rank(data.catalogue(), profile(PROTEIN_MIN_15), options)[0].product.product_id
        ai, gemini, _ = make_ai(Replies.gemini(self.advice(before)), Replies.gemini(self.advice(after)))
        service = RecommendationService(ai, logic, data)
        service.recommend(sam, options)
        data.update_profile(sam, [PROTEIN_MIN_15], [])
        service.recommend(sam, options)
        assert gemini.calls == 2


class Recorder(JobObserver):
    def __init__(self):
        self.steps = []

    def on_job_update(self, job):
        self.steps.append((job.status, job.step))


class TestJobs:
    def test_job_reports_steps_and_result(self):
        recorder = Recorder()
        jobs = JobManager(2, observers=[recorder])
        job = jobs.submit(1, "analysis", lambda j: (j.set_step("Working"), 42)[1])
        wait_for(job)
        assert job.status is JobStatus.DONE and job.result == 42
        assert (JobStatus.RUNNING, "Working") in recorder.steps
        assert recorder.steps[-1] == (JobStatus.DONE, "Done")
        jobs.shutdown()

    def test_errors_mark_job_failed_without_crashing(self):
        jobs = JobManager(2, observers=[])

        def fail_ai(job):
            raise AIError("API_UNAVAILABLE")

        def crash(job):
            raise RuntimeError("bug")

        first, second = jobs.submit(1, "x", fail_ai), jobs.submit(1, "x", crash)
        wait_for(first), wait_for(second)
        assert (first.status, first.error_code) == (JobStatus.FAILED, "API_UNAVAILABLE")
        assert (second.status, second.error_code) == (JobStatus.FAILED, "UNEXPECTED_ERROR")
        jobs.shutdown()

    def test_batch_runs_jobs_at_the_same_time(self):
        jobs = JobManager(3, observers=[])
        barrier = threading.Barrier(3, timeout=2)       # only passes if all 3 run together
        batch = jobs.submit_batch(1, "extraction", [lambda j: barrier.wait()] * 3)
        for job in batch.jobs:
            wait_for(job)
        assert batch.finished and batch.count(JobStatus.DONE) == 3
        jobs.shutdown()

    def test_users_cannot_see_other_peoples_jobs(self):
        jobs = JobManager(1, observers=[])
        job = jobs.submit(1, "x", lambda j: None)
        batch = jobs.submit_batch(1, "x", [lambda j: None])
        assert jobs.get_job(1, job.job_id) is job
        assert jobs.get_job(2, job.job_id) is None
        assert jobs.get_batch(2, batch.batch_id) is None
        jobs.shutdown()

    def test_data_errors_inside_jobs(self):
        jobs = JobManager(1, observers=[])

        def database_down(job):
            raise DataError("DB_UNAVAILABLE")

        job = jobs.submit(1, "analysis", database_down)
        wait_for(job)
        assert job.error_code == "DB_UNAVAILABLE"
        jobs.shutdown()
