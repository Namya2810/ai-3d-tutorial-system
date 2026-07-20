"""
profile_page.py

Roadmap Phase 9 ka UI. Ab ye khud koi form nahi banata - iski jagah teammate
ka naya web frontend (student_profile_module/templates/index.html, Flask se
serve hota hai) ko QWebEngineView ke andar embed karta hai, jaise ek
mini-browser ho.

IMPORTANT: student_profile_module/app.py alag se chalna chahiye
(`python app.py`, default http://localhost:5000) isse pehle ki ye page load
ho - warna "connection refused" dikhega.

Bridge: jab web page ke andar login/signup successful hota hai, wahan ka
JavaScript `pyBridge.studentLoggedIn(studentId)` call karta hai (dekho
index.html). Yeh call yahan StudentBridge.studentLoggedIn() tak pahunchta
hai, jo turant session_state.student_id set kar deta hai - taaki Quiz page
turant jaan le "kiske liye score/response-time log karna hai", bina kisi
polling/refresh ke.
"""

from PyQt6.QtCore import QObject, QUrl, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QVBoxLayout, QWidget

PROFILE_MODULE_URL = "http://localhost:5000/"


class StudentBridge(QObject):
    """JS se call hone wala object - QWebChannel se JS ko available hota hai."""

    def __init__(self, session_state):
        super().__init__()
        self.session_state = session_state

    @pyqtSlot(str)
    def studentLoggedIn(self, student_id):
        if self.session_state:
            self.session_state.student_id = student_id
            self.session_state.student_name = student_id  # index.html apna naam alag se render karta hai


class ProfilePage(QWidget):
    def __init__(self, session_state=None, url=PROFILE_MODULE_URL):
        super().__init__()
        self.setObjectName("ProfilePage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView()

        self.channel = QWebChannel(self.view.page())
        self.bridge = StudentBridge(session_state)
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self.view.load(QUrl(url))

        layout.addWidget(self.view)

    def reload(self):
        """Agar Flask backend abhi start hua ho aur pehli baar page load fail
        hua ho, sidebar se dobara 'Profile' dabane par isko call kar sakte ho."""
        self.view.reload()
