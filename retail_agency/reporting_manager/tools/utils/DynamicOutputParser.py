from typing import List, Dict, Any
import json
import re
import pandas as pd
from io import StringIO
from datetime import datetime

class ResultParser:
    def parse(self, text: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("Parser must implement the parse method.")

class JSONResultParser(ResultParser):
    def parse(self, text: str) -> List[Dict[str, Any]]:
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return [result]
            elif isinstance(result, list):
                return result
            else:
                return []
        except json.JSONDecodeError:
            return []

class CSVResultParser(ResultParser):
    def parse(self, text: str) -> List[Dict[str, Any]]:
        try:
            df = pd.read_csv(StringIO(text))
            return df.to_dict(orient='records')
        except Exception:
            return []

class TableResultParser(ResultParser):
    def parse(self, text: str) -> List[Dict[str, Any]]:
        try:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if len(lines) < 3:
                return []
            # Assume the first line contains headers and the second is a separator
            headers = [h.strip() for h in lines[0].split('|') if h.strip()]
            data_lines = lines[2:]
            result = []
            for line in data_lines:
                if '|' not in line:
                    continue
                values = [v.strip() for v in line.split('|') if v.strip()]
                if len(values) != len(headers):
                    continue
                record = {headers[i].lower().replace(' ', '_'): values[i] for i in range(len(headers))}
                result.append(record)
            return result
        except Exception:
            return []

class NumberedListResultParser(ResultParser):
    def parse(self, text: str) -> List[Dict[str, Any]]:
        try:
            pattern = r'\d+\.(.*?)(?=\n\d+\.|$)'
            matches = re.findall(pattern, text, re.DOTALL)
            result = []
            for match in matches:
                record = {"text": match.strip()}
                result.append(record)
            return result
        except Exception:
            return []

class KeyValueResultParser(ResultParser):
    def parse(self, text: str) -> List[Dict[str, Any]]:
        try:
            items = []
            current_item = {}
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    if current_item:
                        items.append(current_item)
                        current_item = {}
                    continue
                match = re.match(r'([^:]+):\s*(.+)', line)
                if match:
                    key = match.group(1).strip().lower().replace(' ', '_')
                    value = match.group(2).strip()
                    current_item[key] = value
            if current_item:
                items.append(current_item)
            return items
        except Exception:
            return []

class DynamicOutputParser:
    def __init__(self):
        self.parsers = [
            JSONResultParser(),
            CSVResultParser(),
            TableResultParser(),
            NumberedListResultParser(),
            KeyValueResultParser()
        ]
    
    def parse(self, text: str) -> List[Dict[str, Any]]:
        for parser in self.parsers:
            result = parser.parse(text)
            if result and isinstance(result, list) and len(result) > 0:
                for record in result:
                    if isinstance(record, dict) and 'timestamp' not in record:
                        record['timestamp'] = datetime.now().isoformat()
                return result
        return []