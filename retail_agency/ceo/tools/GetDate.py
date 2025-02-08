from agency_swarm.tools import BaseTool
from pydantic import Field
from datetime import datetime
import pytz

class GetDate(BaseTool):
    """
    A tool for getting real-time date and time information.
    Can provide current date, time, and timezone-specific information.
    """
    
    timezone: str = Field(
        default="UTC",
        description="The timezone to get the date/time in (e.g., 'UTC', 'US/Eastern', 'US/Pacific')"
    )
    format: str = Field(
        default="full",
        description="The format of date/time to return ('full', 'date', 'time', 'datetime')"
    )

    def run(self):
        """
        Gets the current date and time in the specified timezone and format.
        Returns formatted date/time string.
        """
        try:
            # Get timezone
            tz = pytz.timezone(self.timezone)
            current_time = datetime.now(tz)
            
            # Format the output based on request
            if self.format == "full":
                return f"Current {self.timezone} time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            elif self.format == "date":
                return f"Current {self.timezone} date: {current_time.strftime('%Y-%m-%d')}"
            elif self.format == "time":
                return f"Current {self.timezone} time: {current_time.strftime('%H:%M:%S %Z')}"
            elif self.format == "datetime":
                return f"Current {self.timezone}: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
            else:
                return f"Invalid format specified. Using default: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            
        except pytz.exceptions.UnknownTimeZoneError:
            return f"Unknown timezone: {self.timezone}. Using UTC instead: {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        except Exception as e:
            return f"Error getting date/time: {str(e)}"

if __name__ == "__main__":
    # Test the tool
    tool = GetDate(timezone="US/Pacific", format="full")
    print(tool.run())
    
    # Test different formats
    print(GetDate(timezone="UTC", format="date").run())
    print(GetDate(timezone="US/Eastern", format="time").run()) 