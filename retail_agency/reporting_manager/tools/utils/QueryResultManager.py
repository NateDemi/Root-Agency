import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import logging
import uuid
from typing import Union, Dict, List, Any

logger = logging.getLogger(__name__)

class QueryResultManager:
    """Manages storage and retrieval of SQL query results."""
    
    def __init__(self, base_path: str = "./query_results"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
    def save_result(self, data: Any, metadata: Dict = None) -> str:
        """Save query result and return a reference ID."""
        try:
            # Generate unique ID
            result_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create directory for this result
            result_dir = self.base_path / result_id
            result_dir.mkdir(exist_ok=True)
            
            # Save metadata
            meta = {
                "id": result_id,
                "timestamp": timestamp,
                "size": len(data) if hasattr(data, '__len__') else 1,
                **(metadata or {})
            }
            
            with open(result_dir / "metadata.json", "w") as f:
                json.dump(meta, f, indent=2)
            
            # Save data based on type
            if isinstance(data, (list, tuple)) and len(data) > 0:
                if isinstance(data[0], (list, tuple, dict)):
                    # Convert to DataFrame for structured data
                    df = pd.DataFrame(data)
                    df.to_csv(result_dir / "data.csv", index=False)
                    format_type = "csv"
                else:
                    # Save as JSON for simple lists
                    with open(result_dir / "data.json", "w") as f:
                        json.dump(data, f, indent=2)
                    format_type = "json"
            else:
                # Save as JSON for other types
                with open(result_dir / "data.json", "w") as f:
                    json.dump(data, f, indent=2)
                format_type = "json"
            
            return {
                "result_id": result_id,
                "format": format_type,
                "path": str(result_dir),
                "size": meta["size"],
                "url": f"/api/query_results/{result_id}"
            }
            
        except Exception as e:
            logger.error(f"Error saving result: {e}")
            raise
            
    def get_result(self, result_id: str) -> Dict[str, Any]:
        """Retrieve saved result by ID."""
        try:
            result_dir = self.base_path / result_id
            
            # Load metadata
            with open(result_dir / "metadata.json", "r") as f:
                metadata = json.load(f)
            
            # Load data based on saved format
            if (result_dir / "data.csv").exists():
                data = pd.read_csv(result_dir / "data.csv").to_dict('records')
            else:
                with open(result_dir / "data.json", "r") as f:
                    data = json.load(f)
            
            return {
                "metadata": metadata,
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Error retrieving result {result_id}: {e}")
            raise
            
    def get_summary(self, result_id: str) -> Dict[str, Any]:
        """Get summary of saved result without loading full data."""
        try:
            result_dir = self.base_path / result_id
            with open(result_dir / "metadata.json", "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error getting summary for {result_id}: {e}")
            raise