# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile

import views.login_view as login_module
from auth.credential_store import CredentialStore
from auth.session import UserSession


class FakePage:
    def __init__(self):
        self.rtl = True
        self.title = ""
        self.update_count = 0

    def update(self):
        self.update_count += 1


class FakeDatabaseConnection:
    server_url = ""

    def refresh_mode(self):
        return None

    def is_remote(self):
        return False

    def get_rest_client(self):
        return None


class FakeUserRepository:
    accepted_password = "Valid-Password-1!"

    def get_all(self):
        return [{"id": 7, "username": "operator", "role": "user"}]

    def authenticate(self, username, password):
        if username == "operator" and password == self.accepted_password:
            return {"id": 7, "username": username, "role": "user", "full_name": "Operator"}
        return None


with tempfile.TemporaryDirectory(prefix="hawaa_login_flow_") as temp_dir:
    settings = {}
    original_store_cls = login_module.CredentialStore
    original_db_cls = login_module.DatabaseConnection
    original_repo_cls = login_module.UserRepository
    original_get = login_module.get_setting
    original_set = login_module.set_setting

    try:
        login_module.CredentialStore = lambda: CredentialStore(temp_dir)
        login_module.DatabaseConnection = FakeDatabaseConnection
        login_module.UserRepository = FakeUserRepository
        login_module.get_setting = lambda key, default=None: settings.get(key, default)
        login_module.set_setting = lambda key, value: settings.__setitem__(key, value)

        successful_users = []
        first = login_module.LoginView(FakePage(), successful_users.append, lambda: None)
        first.username.value = "operator"
        first.password.value = FakeUserRepository.accepted_password
        first.remember.value = True
        first._do_login(None)

        assert successful_users and successful_users[0]["username"] == "operator"
        assert settings["login/remember_password"] == "true"
        assert settings["login/last_username"] == "operator"
        assert first.password.value == ""

        store = CredentialStore(temp_dir)
        saved = store.load("local")
        assert saved is not None and saved.password == FakeUserRepository.accepted_password

        # A fresh LoginView should restore both fields from the encrypted vault.
        second = login_module.LoginView(FakePage(), lambda user: None, lambda: None)
        assert second.remember.value is True
        assert second.username.value == "operator"
        assert second.password.value == FakeUserRepository.accepted_password

        # If the saved password is no longer valid, the vault is removed to
        # prevent repeated lockouts on every app launch.
        FakeUserRepository.accepted_password = "Changed-Password-2!"
        second._do_login(None)
        assert settings["login/remember_password"] == "false"
        assert store.load("local") is None
        assert second.password.value == ""

        # Explicit account switching must remove the encrypted credential.
        FakeUserRepository.accepted_password = "Valid-Password-1!"
        third = login_module.LoginView(FakePage(), lambda user: None, lambda: None)
        third.username.value = "operator"
        third.password.value = FakeUserRepository.accepted_password
        third.remember.value = True
        third._do_login(None)
        assert store.load("local") is not None
        third._switch_account(None)
        assert store.load("local") is None
        assert settings["login/last_username"] == ""
    finally:
        UserSession.logout()
        login_module.CredentialStore = original_store_cls
        login_module.DatabaseConnection = original_db_cls
        login_module.UserRepository = original_repo_cls
        login_module.get_setting = original_get
        login_module.set_setting = original_set

print("✅ login_remember_password_flow_test passed")
