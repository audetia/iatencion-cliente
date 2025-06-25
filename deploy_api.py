import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes
from src.graph import Workflow
from dotenv import load_dotenv

# Importar sistema de logging
from custom_logging import setup_logging, LoggingMiddleware, MetricsMiddleware, get_logger

# Load .env file
load_dotenv()

# Inicializar sistema de logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Email Automation",
    version="1.0",
    description="LangGraph backend for the AI Email automation workflow",
)

# Agregar middleware de logging (debe ir antes que CORS)
app.add_middleware(LoggingMiddleware)
app.add_middleware(MetricsMiddleware)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

def get_runnable():
    logger.info("Initializing LangGraph workflow")
    return Workflow().app

# Fetch LangGraph Automation runnable which generates the workouts
runnable = get_runnable()

# Create the Fast API route to invoke the runnable
add_routes(app, runnable)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    from custom_logging.utils import MonitoringUtils
    import os
    
    log_file = os.getenv('LOG_FILE', 'logs/app.log')
    health_status = MonitoringUtils.check_log_health(log_file)
    
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "logging_system": health_status,
        "version": "1.0"
    }

def main():
    logger.info("Starting Email Automation API server")
    try:
        # Start the API
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logger.error("Failed to start API server", error=str(e), error_type=type(e).__name__)
        raise

if __name__ == "__main__":
    main()