# -*- coding: utf-8 -*-
import flet as ft
from database import UserRepository
from database.connection import DatabaseConnection
from auth.session import UserSession
from i18n.translator import translate, set_language

class LoginView(ft.Container):
    def __init__(self, page, on_login_success, on_exit):
        super().__init__()
        self._page = page
        self.on_login_success = on_login_success
        self.on_exit = on_exit
        self.expand = True
        self.alignment = ft.Alignment.CENTER
        self.padding = 30
        
        self.username = ft.Dropdown(
            label=translate('username'),
            hint_text="اختر أو اكتب اسم المستخدم",
            width=300,
            options=[],
            editable=True
        )
        
        self.password = ft.TextField(
            label=translate('password'),
            password=True,
            can_reveal_password=True,
            width=300
        )
        self.password.on_submit = self._do_login
        
        self.error_msg = ft.Text("", color=ft.Colors.RED, size=12)
        
        self.login_btn = ft.FilledButton(
            content=ft.Text(translate('login'), size=16, weight=ft.FontWeight.BOLD),
            width=300,
            height=45,
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            on_click=self._do_login
        )
        
        self.lang_dropdown = ft.Dropdown(
            label="اللغة",
            width=120,
            value="العربية",
            options=[
                ft.dropdown.Option("العربية"),
                ft.dropdown.Option("English"),
                ft.dropdown.Option("Français")
            ]
        )
        self.lang_dropdown.on_change = self._change_language
        
        self.remember = ft.Checkbox(label="تذكرني", value=False)
        
        self.content = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("🏢 هوى الشام", size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO),
                        ft.Text("نظام الحسابات الداخلية", size=13, color=ft.Colors.GREY_600),
                        ft.Container(height=20),
                        self.username,
                        ft.Container(height=10),
                        self.password,
                        self.error_msg,
                        ft.Container(height=15),
                        self.login_btn,
                        ft.Container(height=10),
                        ft.Row([self.remember, self.lang_dropdown], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.TextButton(content=ft.Text("🔄 تبديل الحساب / مسح البيانات", size=12), on_click=self._switch_account)
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True
                ),
                padding=30,
                width=380
            ),
            elevation=5
        )
        self._populate_users()

    def _populate_users(self):
        db = DatabaseConnection()
        if db.is_remote():
            self.username.options = [ft.dropdown.Option("")]; self.username.value = ""
        else:
            try:
                repo = UserRepository()
                users = repo.get_all()
                self.username.options = [ft.dropdown.Option(u['username']) for u in users]
            except: pass

    def _change_language(self, e):
        lang_map = {"العربية":"ar","English":"en","Français":"fr"}
        set_language(lang_map.get(self.lang_dropdown.value,"ar"))
        self.username.label = translate('username')
        self.password.label = translate('password')
        self.login_btn.content.value = translate('login')
        self._page.update()

    def _switch_account(self, e):
        self.username.value = ""; self.password.value = ""; self.remember.value = False
        self.error_msg.value = "تم مسح بيانات المستخدم"; self.error_msg.color = ft.Colors.GREEN
        self._populate_users()
        self._page.update()

    def _do_login(self, e):
        username = (self.username.value or "").strip()
        password = self.password.value or ""
        if not username or not password:
            self.error_msg.value = "يرجى إدخال اسم المستخدم وكلمة المرور"
            self.error_msg.color = ft.Colors.RED
            self._page.update()
            return
        db = DatabaseConnection()
        if db.is_remote():
            try:
                rest = db.get_rest_client()
                user = rest.login(username, password)
                UserSession.login(user)
                self.on_login_success(user)
            except Exception as e:
                self.error_msg.value = f"فشل تسجيل الدخول: {str(e)}"
                self.error_msg.color = ft.Colors.RED
                self.password.value = ""
                self._page.update()
        else:
            repo = UserRepository()
            user = repo.authenticate(username, password)
            if user:
                UserSession.login(user)
                self.on_login_success(user)
            else:
                self.error_msg.value = "اسم المستخدم أو كلمة المرور غير صحيحة"
                self.error_msg.color = ft.Colors.RED
                self.password.value = ""
                self._page.update()
