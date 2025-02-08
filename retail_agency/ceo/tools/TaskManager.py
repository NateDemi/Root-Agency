from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

class TaskManager(BaseTool):
    """
    A tool for managing and tracking tasks within the retail management agency.
    Handles task creation, updates, and status tracking.
    """
    
    task_id: str = Field(
        None, description="Unique identifier for the task (generated automatically for new tasks)"
    )
    task_type: str = Field(
        ..., description="Type of task (e.g., 'reporting', 'store_operations', 'customer_service')"
    )
    description: str = Field(
        ..., description="Detailed description of the task"
    )
    assigned_to: str = Field(
        ..., description="Agent or team the task is assigned to"
    )
    priority: str = Field(
        "medium", description="Task priority (low, medium, high)"
    )
    status: str = Field(
        "new", description="Current status of the task (new, in_progress, completed, blocked)"
    )

    def run(self):
        """
        Manages task operations including creation, updates, and status changes.
        Returns the updated task information.
        """
        try:
            # Create task data structure
            task_data = {
                "task_id": self.task_id or f"TASK_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "task_type": self.task_type,
                "description": self.description,
                "assigned_to": self.assigned_to,
                "priority": self.priority,
                "status": self.status,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            
            # In a real implementation, this would interact with a database
            # For now, we'll just return the task data
            return json.dumps(task_data, indent=2)
            
        except Exception as e:
            return f"Error managing task: {str(e)}"

if __name__ == "__main__":
    # Test the tool
    tool = TaskManager(
        task_type="reporting",
        description="Generate monthly sales report for Q1 2024",
        assigned_to="reporting_manager",
        priority="high"
    )
    print(tool.run()) 