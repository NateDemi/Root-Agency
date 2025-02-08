from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
from notion_client import Client
import json
from datetime import datetime
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Notion client
notion_token = os.getenv("NOTION_TOKEN")
notion_database_id = os.getenv("NOTION_DATABASE_ID")

class ReportGenerator(BaseTool):
    """
    A tool for generating formatted reports and saving them to Notion.
    Supports various report formats and includes data visualization capabilities.
    """
    
    report_type: str = Field(
        ..., description="Type of report to generate (executive_summary, detailed_analysis, dashboard)"
    )
    data: dict = Field(
        ..., description="The data to include in the report"
    )
    title: str = Field(
        ..., description="Title for the report"
    )
    format_type: str = Field(
        "notion", description="Output format (notion, text, json)"
    )
    tags: list = Field(
        default=[], description="Tags to categorize the report"
    )

    def run(self):
        """
        Generates a formatted report and saves it to Notion.
        Returns the report content and Notion URL.
        """
        try:
            # Generate the report content
            report_content = self._generate_report_content()
            
            # If Notion format is requested, save to Notion
            if self.format_type == "notion":
                return self._save_to_notion(report_content)
            elif self.format_type == "text":
                return self._format_as_text(report_content)
            elif self.format_type == "json":
                return json.dumps(report_content, indent=2)
            else:
                raise ValueError(f"Unsupported format: {self.format_type}")
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}", exc_info=True)
            return f"Error generating report: {str(e)}"
    
    def _generate_report_content(self):
        """
        Generates the report content based on the report type.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if self.report_type == "executive_summary":
            content = self._generate_executive_summary()
        elif self.report_type == "detailed_analysis":
            content = self._generate_detailed_analysis()
        elif self.report_type == "dashboard":
            content = self._generate_dashboard()
        else:
            raise ValueError(f"Unknown report type: {self.report_type}")
        
        return {
            "title": self.title,
            "type": self.report_type,
            "generated_at": timestamp,
            "content": content
        }
    
    def _generate_executive_summary(self):
        """
        Generates an executive summary with key metrics and insights.
        """
        return {
            "key_metrics": self._extract_key_metrics(),
            "highlights": self._generate_highlights(),
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_detailed_analysis(self):
        """
        Generates a detailed analysis with comprehensive data breakdown.
        """
        return {
            "methodology": self._describe_methodology(),
            "detailed_metrics": self._analyze_detailed_metrics(),
            "trends": self._analyze_trends(),
            "insights": self._generate_insights()
        }
    
    def _generate_dashboard(self):
        """
        Generates a dashboard-style report with key performance indicators.
        """
        return {
            "kpis": self._calculate_kpis(),
            "performance_metrics": self._analyze_performance(),
            "alerts": self._generate_alerts()
        }
    
    def _extract_key_metrics(self):
        """Extract and format key metrics from the data."""
        metrics = {}
        for key, value in self.data.items():
            if isinstance(value, (int, float)):
                metrics[key] = value
            elif isinstance(value, dict) and "value" in value:
                metrics[key] = value["value"]
        return metrics
    
    def _generate_highlights(self):
        """Generate key highlights from the data."""
        highlights = []
        for key, value in self.data.items():
            if isinstance(value, dict) and "highlight" in value:
                highlights.append(value["highlight"])
        return highlights
    
    def _generate_recommendations(self):
        """Generate recommendations based on the data."""
        recommendations = []
        for key, value in self.data.items():
            if isinstance(value, dict) and "recommendation" in value:
                recommendations.append(value["recommendation"])
        return recommendations
    
    def _describe_methodology(self):
        """Describe the methodology used in the analysis."""
        return {
            "data_sources": self.data.get("data_sources", ["Not specified"]),
            "time_period": self.data.get("time_period", "Not specified"),
            "analysis_methods": self.data.get("analysis_methods", ["Not specified"])
        }
    
    def _analyze_detailed_metrics(self):
        """Analyze and format detailed metrics."""
        return {key: value for key, value in self.data.items() 
                if isinstance(value, dict) and "detailed" in value}
    
    def _analyze_trends(self):
        """Analyze trends in the data."""
        return {key: value for key, value in self.data.items() 
                if isinstance(value, dict) and "trend" in value}
    
    def _generate_insights(self):
        """Generate insights from the data."""
        return {key: value for key, value in self.data.items() 
                if isinstance(value, dict) and "insight" in value}
    
    def _calculate_kpis(self):
        """Calculate key performance indicators."""
        return {key: value for key, value in self.data.items() 
                if isinstance(value, dict) and "kpi" in value}
    
    def _analyze_performance(self):
        """Analyze performance metrics."""
        return {key: value for key, value in self.data.items() 
                if isinstance(value, dict) and "performance" in value}
    
    def _generate_alerts(self):
        """Generate alerts based on the data."""
        return {key: value for key, value in self.data.items() 
                if isinstance(value, dict) and "alert" in value}
    
    def _save_to_notion(self, report_content):
        """
        Saves the report to Notion and returns the URL.
        """
        try:
            if not notion_token or not notion_database_id:
                return "Error: Notion credentials not found in environment variables."
            
            # Initialize Notion client
            notion = Client(auth=notion_token)
            
            # Format content for Notion
            blocks = self._convert_to_notion_blocks(report_content)
            
            # Create the page
            new_page = notion.pages.create(
                parent={"database_id": notion_database_id},
                properties={
                    "title": {
                        "title": [{"text": {"content": self.title}}]
                    },
                    "Tags": {
                        "multi_select": [{"name": tag} for tag in self.tags]
                    }
                },
                children=blocks
            )
            
            # Get the page URL
            page_id = new_page["id"]
            url = f"https://notion.so/{page_id.replace('-', '')}"
            
            return f"""Report generated successfully!
Title: {self.title}
Type: {self.report_type}
View in Notion: {url}"""
            
        except Exception as e:
            logger.error(f"Error saving to Notion: {str(e)}", exc_info=True)
            return f"Error saving to Notion: {str(e)}"
    
    def _convert_to_notion_blocks(self, report_content):
        """
        Converts report content to Notion blocks format.
        """
        blocks = []
        
        # Add header
        blocks.append({
            "object": "block",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": report_content["title"]}}]
            }
        })
        
        # Add metadata
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"Generated: {report_content['generated_at']}"}}]
            }
        })
        
        # Add content sections
        for section, data in report_content["content"].items():
            # Add section header
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": section.replace('_', ' ').title()}}]
                }
            })
            
            # Add section content
            blocks.extend(self._format_section_content(data))
        
        return blocks
    
    def _format_section_content(self, data):
        """
        Formats section content into Notion blocks.
        """
        blocks = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": f"{key.replace('_', ' ').title()}: {value}"}}]
                    }
                })
        elif isinstance(data, list):
            for item in data:
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": str(item)}}]
                    }
                })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": str(data)}}]
                }
            })
        
        return blocks
    
    def _format_as_text(self, report_content):
        """
        Formats the report content as plain text.
        """
        text = f"""
{report_content['title']}
{'=' * len(report_content['title'])}
Generated: {report_content['generated_at']}
Type: {report_content['type']}

"""
        
        for section, data in report_content["content"].items():
            text += f"\n{section.replace('_', ' ').title()}\n{'-' * len(section)}\n"
            if isinstance(data, dict):
                for key, value in data.items():
                    text += f"{key.replace('_', ' ').title()}: {value}\n"
            elif isinstance(data, list):
                for item in data:
                    text += f"- {item}\n"
            else:
                text += f"{data}\n"
        
        return text

if __name__ == "__main__":
    # Test the tool
    test_data = {
        "total_sales": {"value": 150000, "trend": "increasing"},
        "average_order": {"value": 75.50, "highlight": "15% increase from last month"},
        "customer_satisfaction": {"value": 4.2, "recommendation": "Focus on improving response time"},
        "top_products": ["Product A", "Product B", "Product C"],
        "data_sources": ["Sales Database", "CRM System"],
        "time_period": "Last 30 days",
        "analysis_methods": ["Trend Analysis", "Comparative Analysis"]
    }
    
    tool = ReportGenerator(
        report_type="executive_summary",
        title="Monthly Sales Performance Report",
        data=test_data,
        tags=["sales", "monthly", "performance"]
    )
    print(tool.run()) 