from agency_swarm.tools import BaseTool
from pydantic import Field, ConfigDict
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict, Union, Any
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataAnalyzer(BaseTool):
    """
    A tool for analyzing retail data using advanced statistical and machine learning methods.
    Supports various types of analysis including trend analysis, forecasting, and anomaly detection.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    data: Union[pd.DataFrame, Dict[str, Any]] = Field(
        ..., description="Data to analyze. Can be a DataFrame or a dictionary of data."
    )
    analysis_type: str = Field(
        ..., description="Type of analysis to perform (trend, forecast, segment, anomaly, correlation)"
    )
    time_column: Optional[str] = Field(
        None, description="Name of the time column for time series analysis"
    )
    target_column: Optional[str] = Field(
        None, description="Name of the target column to analyze"
    )
    feature_columns: Optional[List[str]] = Field(
        None, description="List of feature columns for analysis"
    )
    params: Optional[dict] = Field(
        default={}, description="Additional parameters for the analysis"
    )

    def run(self):
        """
        Performs the requested analysis on the provided data.
        Returns the analysis results in a structured format.
        """
        try:
            # Convert data to DataFrame if it's a dictionary
            if isinstance(self.data, dict):
                if 'values' in self.data:
                    df = pd.DataFrame(self.data['values'])
                else:
                    df = pd.DataFrame(self.data)
            else:
                df = self.data

            # Perform the requested analysis
            if self.analysis_type == "trend":
                return self._analyze_trends(df)
            elif self.analysis_type == "forecast":
                return self._generate_forecast(df)
            elif self.analysis_type == "segment":
                return self._segment_data(df)
            elif self.analysis_type == "anomaly":
                return self._detect_anomalies(df)
            elif self.analysis_type == "correlation":
                return self._analyze_correlations(df)
            else:
                raise ValueError(f"Unsupported analysis type: {self.analysis_type}")

        except Exception as e:
            logger.error(f"Error analyzing data: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _analyze_trends(self, df: pd.DataFrame) -> dict:
        """
        Analyzes trends in the data using various statistical methods.
        """
        try:
            if not self.time_column or not self.target_column:
                raise ValueError("Time and target columns must be specified for trend analysis")

            # Convert time column to datetime if needed
            df[self.time_column] = pd.to_datetime(df[self.time_column])
            df = df.sort_values(self.time_column)

            # Calculate various trend metrics
            results = {
                "overall_trend": self._calculate_overall_trend(df),
                "seasonal_patterns": self._identify_seasonal_patterns(df),
                "growth_rates": self._calculate_growth_rates(df),
                "summary_statistics": self._calculate_summary_stats(df)
            }

            return results

        except Exception as e:
            logger.error(f"Error in trend analysis: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _generate_forecast(self, df: pd.DataFrame) -> dict:
        """
        Generates forecasts using various time series forecasting methods.
        """
        try:
            if not self.time_column or not self.target_column:
                raise ValueError("Time and target columns must be specified for forecasting")

            # Convert time column to datetime if needed
            df[self.time_column] = pd.to_datetime(df[self.time_column])
            df = df.sort_values(self.time_column)

            # Get forecast parameters
            forecast_periods = self.params.get('forecast_periods', 30)
            
            # Perform exponential smoothing forecast
            model = ExponentialSmoothing(
                df[self.target_column],
                seasonal_periods=self.params.get('seasonal_periods', 7),
                trend='add',
                seasonal='add'
            )
            fitted_model = model.fit()
            forecast = fitted_model.forecast(forecast_periods)
            
            # Calculate confidence intervals
            residuals = fitted_model.resid
            std_resid = np.std(residuals)
            conf_int = 1.96 * std_resid  # 95% confidence interval
            
            return {
                "forecast": forecast.tolist(),
                "confidence_interval": conf_int,
                "model_metrics": {
                    "aic": fitted_model.aic,
                    "bic": fitted_model.bic,
                    "mse": np.mean(residuals ** 2)
                }
            }

        except Exception as e:
            logger.error(f"Error in forecasting: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _segment_data(self, df: pd.DataFrame) -> dict:
        """
        Segments the data using clustering and dimensionality reduction techniques.
        """
        try:
            if not self.feature_columns:
                raise ValueError("Feature columns must be specified for segmentation")

            # Prepare features for clustering
            features = df[self.feature_columns]
            
            # Handle missing values
            features = features.fillna(features.mean())
            
            # Standardize features
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)
            
            # Perform PCA for dimensionality reduction
            pca = PCA(n_components=min(len(self.feature_columns), 3))
            reduced_features = pca.fit_transform(scaled_features)
            
            # Perform clustering
            n_clusters = self.params.get('n_clusters', 3)
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            clusters = kmeans.fit_predict(scaled_features)
            
            # Calculate cluster statistics
            cluster_stats = []
            for i in range(n_clusters):
                cluster_data = features[clusters == i]
                stats = {
                    "size": len(cluster_data),
                    "percentage": len(cluster_data) / len(features) * 100,
                    "mean": cluster_data.mean().to_dict(),
                    "std": cluster_data.std().to_dict()
                }
                cluster_stats.append(stats)
            
            return {
                "n_clusters": n_clusters,
                "cluster_assignments": clusters.tolist(),
                "cluster_statistics": cluster_stats,
                "explained_variance_ratio": pca.explained_variance_ratio_.tolist()
            }

        except Exception as e:
            logger.error(f"Error in data segmentation: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _detect_anomalies(self, df: pd.DataFrame) -> dict:
        """
        Detects anomalies in the data using statistical methods.
        """
        try:
            if not self.target_column:
                raise ValueError("Target column must be specified for anomaly detection")

            # Calculate statistical properties
            mean = df[self.target_column].mean()
            std = df[self.target_column].std()
            
            # Define anomaly thresholds (e.g., 3 standard deviations)
            threshold = self.params.get('threshold', 3)
            upper_bound = mean + threshold * std
            lower_bound = mean - threshold * std
            
            # Identify anomalies
            anomalies = df[
                (df[self.target_column] > upper_bound) |
                (df[self.target_column] < lower_bound)
            ]
            
            return {
                "n_anomalies": len(anomalies),
                "anomaly_indices": anomalies.index.tolist(),
                "anomaly_values": anomalies[self.target_column].tolist(),
                "threshold_values": {
                    "upper": upper_bound,
                    "lower": lower_bound,
                    "mean": mean,
                    "std": std
                }
            }

        except Exception as e:
            logger.error(f"Error in anomaly detection: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _analyze_correlations(self, df: pd.DataFrame) -> dict:
        """
        Analyzes correlations between features in the data.
        """
        try:
            if not self.feature_columns:
                raise ValueError("Feature columns must be specified for correlation analysis")

            # Calculate correlation matrix
            corr_matrix = df[self.feature_columns].corr()
            
            # Find strong correlations
            threshold = self.params.get('correlation_threshold', 0.7)
            strong_correlations = []
            
            for i in range(len(self.feature_columns)):
                for j in range(i + 1, len(self.feature_columns)):
                    correlation = corr_matrix.iloc[i, j]
                    if abs(correlation) >= threshold:
                        strong_correlations.append({
                            "feature1": self.feature_columns[i],
                            "feature2": self.feature_columns[j],
                            "correlation": correlation
                        })
            
            return {
                "correlation_matrix": corr_matrix.to_dict(),
                "strong_correlations": strong_correlations,
                "summary": {
                    "n_strong_correlations": len(strong_correlations),
                    "max_correlation": corr_matrix.max().max(),
                    "min_correlation": corr_matrix.min().min()
                }
            }

        except Exception as e:
            logger.error(f"Error in correlation analysis: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _calculate_overall_trend(self, df: pd.DataFrame) -> dict:
        """
        Calculates the overall trend in the target variable.
        """
        values = df[self.target_column].values
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        return {
            "direction": "increasing" if slope > 0 else "decreasing",
            "slope": slope,
            "start_value": values[0],
            "end_value": values[-1],
            "percent_change": ((values[-1] - values[0]) / values[0]) * 100
        }

    def _identify_seasonal_patterns(self, df: pd.DataFrame) -> dict:
        """
        Identifies seasonal patterns in the data.
        """
        # Calculate daily, weekly, and monthly averages
        df['day_of_week'] = df[self.time_column].dt.day_name()
        df['month'] = df[self.time_column].dt.month_name()
        
        daily_avg = df.groupby('day_of_week')[self.target_column].mean().to_dict()
        monthly_avg = df.groupby('month')[self.target_column].mean().to_dict()
        
        return {
            "daily_pattern": daily_avg,
            "monthly_pattern": monthly_avg,
            "peak_day": max(daily_avg.items(), key=lambda x: x[1])[0],
            "peak_month": max(monthly_avg.items(), key=lambda x: x[1])[0]
        }

    def _calculate_growth_rates(self, df: pd.DataFrame) -> dict:
        """
        Calculates various growth rates in the data.
        """
        # Calculate period-over-period growth rates
        daily_growth = df[self.target_column].pct_change().mean() * 100
        weekly_growth = df[self.target_column].pct_change(7).mean() * 100
        monthly_growth = df[self.target_column].pct_change(30).mean() * 100
        
        return {
            "daily_growth_rate": daily_growth,
            "weekly_growth_rate": weekly_growth,
            "monthly_growth_rate": monthly_growth
        }

    def _calculate_summary_stats(self, df: pd.DataFrame) -> dict:
        """
        Calculates summary statistics for the target variable.
        """
        return {
            "mean": df[self.target_column].mean(),
            "median": df[self.target_column].median(),
            "std": df[self.target_column].std(),
            "min": df[self.target_column].min(),
            "max": df[self.target_column].max(),
            "q1": df[self.target_column].quantile(0.25),
            "q3": df[self.target_column].quantile(0.75)
        }

if __name__ == "__main__":
    # Test the tool with sample data
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    np.random.seed(42)
    
    # Generate sample data
    sales = np.random.normal(1000, 100, len(dates))
    sales = sales + np.sin(np.arange(len(dates)) * 2 * np.pi / 7) * 100  # Weekly seasonality
    sales = sales + np.sin(np.arange(len(dates)) * 2 * np.pi / 365) * 200  # Yearly seasonality
    sales = sales + np.arange(len(dates)) * 0.5  # Upward trend
    
    # Create test DataFrame
    test_data = pd.DataFrame({
        'date': dates,
        'sales': sales,
        'customers': np.random.normal(500, 50, len(dates)),
        'items_per_order': np.random.normal(3, 0.5, len(dates)),
        'average_price': np.random.normal(50, 5, len(dates))
    })
    
    # Test trend analysis
    analyzer = DataAnalyzer(
        data=test_data,
        analysis_type="trend",
        time_column="date",
        target_column="sales"
    )
    print("\nTrend Analysis Results:")
    print(analyzer.run())
    
    # Test forecasting
    analyzer = DataAnalyzer(
        data=test_data,
        analysis_type="forecast",
        time_column="date",
        target_column="sales",
        params={'forecast_periods': 30, 'seasonal_periods': 7}
    )
    print("\nForecasting Results:")
    print(analyzer.run())
    
    # Test segmentation
    analyzer = DataAnalyzer(
        data=test_data,
        analysis_type="segment",
        feature_columns=['sales', 'customers', 'items_per_order', 'average_price'],
        params={'n_clusters': 3}
    )
    print("\nSegmentation Results:")
    print(analyzer.run())
    
    # Test anomaly detection
    analyzer = DataAnalyzer(
        data=test_data,
        analysis_type="anomaly",
        target_column="sales",
        params={'threshold': 3}
    )
    print("\nAnomaly Detection Results:")
    print(analyzer.run())
    
    # Test correlation analysis
    analyzer = DataAnalyzer(
        data=test_data,
        analysis_type="correlation",
        feature_columns=['sales', 'customers', 'items_per_order', 'average_price'],
        params={'correlation_threshold': 0.7}
    )
    print("\nCorrelation Analysis Results:")
    print(analyzer.run()) 