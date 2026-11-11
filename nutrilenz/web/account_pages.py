from flask import Flask, flash, redirect, render_template, request, url_for

from ..domain.goal_factory import GoalFactory
from ..errors.auth_error import AuthError
from ..errors.data_error import DataError
from ..errors.error_messages import ErrorMessages
from ..errors.validation_error import ValidationError
from .page_controller import PageController


class AccountPages(PageController):
    """Sign up, log in, log out, edit goals and delete the account."""

    PUBLIC_ENDPOINTS = ("login", "signup")

    def register(self, app: Flask) -> None:
        app.add_url_rule("/login", "login", self.login, methods=["GET", "POST"])
        app.add_url_rule("/signup", "signup", self.signup, methods=["GET", "POST"])
        app.add_url_rule("/logout", "logout", self.logout, methods=["POST"])
        app.add_url_rule("/profile", "profile", self.profile, methods=["GET", "POST"])
        app.add_url_rule("/profile/delete", "delete_account", self.delete_account, methods=["POST"])

    def login(self):
        if request.method == "GET":
            return render_template("login.html", errors={}, values={})
        try:
            username, password = self._ctx.forms.credentials(request.form, new_account=False)
            user = self._ctx.data.authenticate(username, password)
        except ValidationError as error:
            return render_template("login.html", errors=error.field_errors, values=request.form), 400
        except AuthError as error:
            return render_template("login.html", errors={"form": ErrorMessages.text(error.code)},
                                   values=request.form), 401
        self._ctx.login.log_in(user.user_id)
        flash("Welcome back, " + user.username + ".")
        return redirect(url_for("dashboard"))

    def signup(self):
        if request.method == "GET":
            return render_template("signup.html", errors={}, values={}, presets=GoalFactory.PRESETS,
                                   selected_checks=[])
        errors = {}
        try:
            username, password = self._ctx.forms.credentials(request.form, new_account=True)
        except ValidationError as error:
            errors.update(error.field_errors)
        try:
            goals, avoid = self._ctx.forms.goals(request.form)
        except ValidationError as error:
            errors.update(error.field_errors)
        try:
            checks = self._ctx.forms.dietary_checks(request.form)
        except ValidationError as error:
            errors.update(error.field_errors)
        if not errors:
            try:
                user = self._ctx.data.register(username, password, goals, avoid, checks)
            except DataError as error:
                errors["username" if error.code == "DUPLICATE_USER" else "form"] = ErrorMessages.text(error.code)
        if errors:
            return render_template("signup.html", errors=errors, values=request.form,
                                   presets=GoalFactory.PRESETS,
                                   selected_checks=request.form.getlist("dietary_checks")), 400
        self._ctx.login.log_in(user.user_id)
        flash("Account created. Welcome to NutriLenz!")
        return redirect(url_for("dashboard"))

    def logout(self):
        self._ctx.login.log_out()
        flash("You have been logged out.")
        return redirect(url_for("login"))

    def _profile_values(self) -> dict:
        values = {"avoid_ingredients": ", ".join(self._user.profile.avoid_ingredients)}
        for goal in self._user.profile.goals:
            preset = GoalFactory.preset_name(goal)
            if preset:
                values["goal_" + preset] = "on"
                values["target_" + preset] = f"{goal.target:g}"
        return values

    def profile(self):
        if request.method == "GET":
            return render_template("profile.html", errors={}, values=self._profile_values(),
                                   presets=GoalFactory.PRESETS,
                                   selected_checks=[c.key for c in self._user.profile.dietary_checks])
        try:
            goals, avoid = self._ctx.forms.goals(request.form)
            checks = self._ctx.forms.dietary_checks(request.form)
            self._ctx.data.update_profile(self._user, goals, avoid, checks)
        except ValidationError as error:
            return render_template("profile.html", errors=error.field_errors, values=request.form,
                                   presets=GoalFactory.PRESETS,
                                   selected_checks=request.form.getlist("dietary_checks")), 400
        flash("Profile saved. Past analyses keep their original goals and dietary results.")
        return redirect(url_for("profile"))

    def delete_account(self):
        try:
            self._ctx.data.authenticate(self._user.username, request.form.get("password", ""))
        except AuthError:
            flash("Account NOT deleted: the password was wrong.")
            return redirect(url_for("profile"))
        self._ctx.data.delete_account(self._user.user_id)
        self._ctx.login.log_out()
        flash("Your account and saved analyses were deleted.")
        return redirect(url_for("login"))
