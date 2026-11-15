from flask import Flask, redirect, render_template, request, url_for

from ..services.comparison_service import ComparisonService
from .page_controller import PageController


class ComparePages(PageController):
    """Shelf Compare: photograph 2-4 similar products, check what the AI read,
    then see them ranked side by side for the user's goals."""

    def register(self, app: Flask) -> None:
        app.add_url_rule("/compare", "compare", self.compare)
        app.add_url_rule("/batches/<batch_id>/compare", "compare_batch", self.compare_batch,
                         methods=["POST"])

    def compare(self):
        return render_template("compare.html", errors={},
                               min_items=ComparisonService.MIN_PRODUCTS,
                               max_items=ComparisonService.MAX_PRODUCTS)

    def compare_batch(self, batch_id: str):
        batch = self._batch_or_404(batch_id)
        products, errors = self._ticked_products(batch, request.form)
        low, high = ComparisonService.MIN_PRODUCTS, ComparisonService.MAX_PRODUCTS
        if not errors and not low <= len(products) <= high:
            errors["form"] = f"Tick {low} to {high} products to compare them."
        if errors:
            return render_template("batch.html", batch=batch, values=request.form,
                                   errors=errors, mode="compare"), 400
        user = self._user
        job = self._ctx.jobs.submit(user.user_id, "comparison",
                                    lambda job: self._ctx.comparisons.compare(user, products, job))
        return redirect(url_for("job", job_id=job.job_id))
