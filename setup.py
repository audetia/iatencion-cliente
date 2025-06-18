from setuptools import setup, find_packages

setup(
    name="iatencion-cliente",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "langchain-core",
        "langchain_community",
        "langgraph",
        "langchain-groq",
        "langchain_google_genai",
        "langchain_chroma",
        "chromadb",
        "beautifulsoup4",
        "python-dotenv",
        "colorama",
        "langserve",
        "sse_starlette",
        "uvicorn",
        "gunicorn",
        "fastapi",
        "pytest",
    ],
) 