"""NutriLenz entry point. Run with:  python main.py  (then open http://localhost:5000)"""

from nutrilenz.app import NutriLenzApp

if __name__ == "__main__":
    NutriLenzApp.from_environment().run()
