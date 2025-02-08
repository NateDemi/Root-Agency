from ceo.tools.SlackCommunicator import SlackCommunicator
from ceo.tools.TaskManager import TaskManager
from dotenv import load_dotenv
import json
import time

# Load environment variables
load_dotenv()

# Direct Message channel ID
CHANNEL_ID = "D088VGQRH63"  # DM channel

def simulate_user_request():
    print("\n=== Simulating User Request for Sales Report ===")
    
    # User sends initial request
    communicator = SlackCommunicator(
        channel_id=CHANNEL_ID,
        message="Hi! I need a sales performance report for Q1 2024. Could you help me with that?"
    )
    result = communicator.run()
    print("\nUser Request Sent:", result)
    
    # CEO acknowledges and creates task
    task = TaskManager(
        task_type="reporting",
        description="Generate Q1 2024 Sales Performance Report",
        assigned_to="reporting_manager",
        priority="high"
    )
    task_result = task.run()
    task_data = json.loads(task_result)
    
    # CEO sends acknowledgment and task details
    acknowledgment = SlackCommunicator(
        channel_id=CHANNEL_ID,
        message=f"I'll help you with that right away! I've created a high-priority task:\n"
                f"• Task ID: {task_data['task_id']}\n"
                f"• Description: {task_data['description']}\n"
                f"• Status: {task_data['status']}\n\n"
                f"I'll coordinate with our Reporting Manager to get this prepared for you."
    )
    result = acknowledgment.run()
    print("\nCEO Acknowledgment Sent:", result)
    
    # Simulate task progress update
    time.sleep(2)  # Simulate some time passing
    update_task = TaskManager(
        task_id=task_data["task_id"],
        task_type="reporting",
        description="Generate Q1 2024 Sales Performance Report",
        assigned_to="reporting_manager",
        priority="high",
        status="in_progress"
    )
    update_task.run()
    
    # CEO sends progress update
    progress_update = SlackCommunicator(
        channel_id=CHANNEL_ID,
        message="Update: Our Reporting Manager is now working on your sales performance report. "
                "They're analyzing the Q1 2024 data and preparing comprehensive insights."
    )
    result = progress_update.run()
    print("\nProgress Update Sent:", result)
    
    # Simulate task completion
    time.sleep(2)  # Simulate report generation time
    complete_task = TaskManager(
        task_id=task_data["task_id"],
        task_type="reporting",
        description="Generate Q1 2024 Sales Performance Report",
        assigned_to="reporting_manager",
        priority="high",
        status="completed"
    )
    complete_task.run()
    
    # CEO sends completion message with sample findings
    completion_message = SlackCommunicator(
        channel_id=CHANNEL_ID,
        message="Great news! The Q1 2024 Sales Performance Report is ready. Here are the key highlights:\n\n"
                "📈 Key Findings:\n"
                "• Total Revenue: $1,500,000\n"
                "• Growth Rate: 15% (compared to Q4 2023)\n"
                "• Top Performing Products: Product A, Product B, Product C\n\n"
                "Would you like me to provide the full detailed report or focus on any specific aspects?"
    )
    result = completion_message.run()
    print("\nCompletion Message Sent:", result)

def simulate_follow_up_question():
    print("\n=== Simulating User Follow-up Question ===")
    
    # User asks about specific metrics
    communicator = SlackCommunicator(
        channel_id=CHANNEL_ID,
        message="Could you tell me more about our customer metrics for Q1?"
    )
    result = communicator.run()
    print("\nFollow-up Question Sent:", result)
    
    # CEO responds with customer metrics
    response = SlackCommunicator(
        channel_id=CHANNEL_ID,
        message="Here are the detailed customer metrics for Q1 2024:\n\n"
                "👥 Customer Metrics:\n"
                "• Customer Satisfaction Score: 4.2/5.0\n"
                "• Customer Retention Rate: 85%\n"
                "• Average Customer Lifetime Value: $850\n\n"
                "Notable Trends:\n"
                "• Customer satisfaction has improved by 15% compared to last quarter\n"
                "• Retention rate is above our target of 80%\n"
                "• Customer lifetime value has increased by 10%\n\n"
                "Would you like any specific analysis of these metrics?"
    )
    result = response.run()
    print("\nDetailed Response Sent:", result)

if __name__ == "__main__":
    print("Starting CEO Interaction Test...")
    
    # Simulate initial request and response
    simulate_user_request()
    
    # Simulate follow-up interaction
    time.sleep(3)  # Add a small delay between conversations
    simulate_follow_up_question()
    
    print("\nCEO Interaction Test Completed!") 