# AI use disclosure

EarthTrend was developed with AI coding assistants. Below are the prompts the
team used to plan and build each part of the project, kept for disclosure.

The later work was carried out with Anthropic's Claude Code, working in the
repository under the team's direction:

- the audit and data validation (docs/AUDIT_2026-11-15.md);
- the statistical review (docs/ANALYSIS.md);
- the station cross-check protocol and its run (docs/validation/);
- the data-source feasibility study;
- the release cleanup and packaging.

Claude Code wrote code, tests and documentation, ran the tests and scripts,
and reported results. The team reviewed and approved each step, including the
protocol before it was run.

AI output was not accepted as evidence:

- every data value comes from the NASA files or APIs named in DATA_SOURCES.md;
- the statistical behaviour is checked by the automated tests, including the
  false-positive simulations in tests/test_false_positive_rates.py;
- the station cross-check followed a protocol that was fixed before any data
  were read (docs/STATION_VALIDATION_PROTOCOL.md).

The prompts are historical. Some steps they mention, such as an
`.env.example` file, were later removed because the project does not need
them.

# EarthTrend AI prompts

## 0. Project Context

You are a senior Python engineer, Earth science data analyst, and scientific software architect.

We are building a NASA Space Apps Challenge project called **EarthTrend — Earth System Trend Detective**.

### Challenge objective
Build an application that allows users to:
1. Select one or more Earth science variables.
2. Select a geographic region or location.
3. Select a time period.
4. Retrieve relevant real Earth science data.
5. Generate and visualize a time series.
6. Identify the direction and rate of change.
7. Test whether the observed trend is statistically significant.

The application must answer:
- What is changing?
- Where is it changing?
- How much is it changing?
- Is the trend statistically significant?

### Team and development context
We are a six-member student team participating in NASA Space Apps Challenge 2026.

Our initial preferred technologies are:
- Python
- Streamlit OR React + FastAPI (we will explicitly choose one architecture)
- Pandas
- NumPy
- SciPy
- PyMannKendall
- Statsmodels
- Plotly
- NASA open data sources

### Important development rules
- Prioritize a working and scientifically correct MVP.
- Never fabricate NASA data, API responses, citations, or statistical results.
- Clearly distinguish real data from synthetic test data.
- Preserve the original source, units, temporal resolution, and geographic information.
- Handle missing values explicitly.
- Do not silently convert missing observations to zero.
- Validate user inputs.
- Keep the code modular and readable.
- Do not introduce unnecessary databases or technologies.
- Explain important implementation decisions.
- Add tests for critical scientific calculations.
- Do not overwrite existing project files without inspecting them first.

Before making major changes, inspect the existing repository and explain the proposed changes.

Work incrementally and verify each major feature before continuing.



## 1. Technical Planning

Act as the technical lead of EarthTrend.

Analyze the challenge requirements and propose a practical MVP architecture for a student hackathon.

Our goal is to implement the five-step workflow:
1. Variable selection.
2. Geographic region selection.
3. Time-period selection.
4. Time-series generation and visualization.
5. Statistical trend significance testing.

Provide:
- Recommended architecture.
- Recommended technology stack.
- Project folder structure.
- Responsibilities of each module.
- Required Python dependencies.
- Data flow from NASA sources to the final user interface.
- Minimum MVP features.
- Features that should be postponed.
- Main technical risks and fallback strategies.

Compare Streamlit with React + FastAPI and recommend only one based on implementation speed and team capabilities.

Do not start coding yet. First produce a clear implementation plan.


## 2. Project Setup

Set up the initial EarthTrend project structure based on the architecture we selected.

Tasks:
1. Create the required folders and Python modules.
2. Create requirements.txt with appropriate dependencies.
3. Create .gitignore.
4. Create .env.example if configuration variables are needed.
5. Create a clear README.md.
6. Add a basic application entry point.
7. Add a health or startup check.
8. Add a minimal test structure.

Do not implement the full application yet.

Ensure the project can be installed and started using documented commands.

Before finishing:
- List all created files.
- Explain how to install dependencies.
- Explain how to run the application.
- Identify any manual steps still required.


## 3. NASA Data Integration

Act as an Earth science data engineer.

We need to integrate a real NASA Earth science dataset into EarthTrend.

Our initial variables may include:
- Air temperature.
- Precipitation.

Investigate the official NASA POWER API documentation and identify:
- Correct parameter identifiers.
- Supported temporal resolutions.
- Available time coverage.
- Measurement units.
- Geographic query parameters.
- Missing-data conventions.
- Data limitations.

Implement a modular NASA data client that:
1. Sends a valid request to the official data endpoint.
2. Checks the HTTP response.
3. Handles timeouts and API errors.
4. Parses the actual returned data.
5. Converts the result into a standardized time-series DataFrame.
6. Preserves source metadata and units.
7. Handles missing values without replacing them with zero.

Do not invent endpoint parameters or assume that a dataset covers a particular period.

If live API access is unavailable, implement the client structure and provide a clearly labeled synthetic test fixture. Do not pretend the synthetic fixture is NASA data.

Include a small test for the parsing logic and document the official data source.



## 4. Data Preprocessing

Implement the EarthTrend time-series preprocessing module.

Input:
A DataFrame containing a date column and a numeric measurement column, along with dataset metadata.

Requirements:
1. Parse dates correctly.
2. Sort observations chronologically.
3. Check duplicate timestamps.
4. Detect missing values.
5. Detect invalid or non-numeric measurements.
6. Preserve valid original observations.
7. Never silently replace missing values with zero.
8. Report the number of observations before and after preprocessing.
9. Preserve the measurement unit and temporal resolution.
10. Ensure the output is suitable for trend analysis.

Add tests for:
- Missing observations.
- Duplicate dates.
- Invalid values.
- Unsorted timestamps.
- Empty datasets.

Document every preprocessing decision.


## 5. Statistical Analysis

Implement the scientific trend-analysis module for EarthTrend.

Required methods:

1. Linear Regression:
   - Estimate the trend rate over time.
   - Return the slope with an appropriate unit.
   - Return the intercept and relevant regression statistics.

2. Mann-Kendall Test:
   - Determine whether a monotonic trend is increasing, decreasing, or not statistically significant.
   - Return the test statistic, p-value, and decision at a documented significance level.

3. Sen's Slope:
   - Estimate a robust trend slope where appropriate.

4. Confidence intervals:
   - Provide an appropriate confidence interval for the trend estimate when supported by the selected method.

Important scientific requirements:
- Clearly distinguish the trend direction from statistical significance.
- Do not claim that a trend is significant merely because the chart looks increasing.
- Handle insufficient observations.
- Handle constant or invalid data.
- Explain assumptions and limitations.
- Investigate seasonality and temporal autocorrelation before interpreting climate time-series significance.
- Do not use ordinary independent-observation assumptions without considering temporal dependence.

Create tests using synthetic datasets with:
- A known increasing trend.
- A known decreasing trend.
- Constant values.
- Random noise.
- Missing observations.

Return structured results that can be consumed by the application interface.

Document the method and interpretation of every result.




## 6. Visualization

Implement the EarthTrend visualization module.

Create interactive scientific time-series charts.

Each chart should include:
- Date on the X-axis.
- Measurement value on the Y-axis.
- Correct measurement unit.
- Observed data points.
- Optional fitted trend line.
- Clear title and variable name.
- Geographic location.
- Data source.
- Selected time period.

Requirements:
- Use Plotly.
- Support missing observations without inventing values.
- Make the chart readable and suitable for a scientific presentation.
- Clearly distinguish observed measurements from fitted trend lines.
- Include a legend.
- Avoid misleading axis scales.

If using Streamlit, integrate the chart into the Streamlit interface.

If using React, return the data in a format suitable for Plotly.js.




## 7. Streamlit UI

Build the EarthTrend user interface using Streamlit.

Design a clean, professional Earth science analytics application.

Required interface sections:

1. Header:
   - EarthTrend title.
   - Short project description.

2. Analysis configuration:
   - Variable selector.
   - Geographic location selector.
   - Latitude and longitude inputs when applicable.
   - Start date and end date.
   - Temporal resolution selector when supported.

3. Data retrieval:
   - Analyze button.
   - Loading indicator.
   - Clear error messages.

4. Time-series visualization:
   - Interactive Plotly chart.
   - Observed measurements.
   - Trend line.

5. Statistical results:
   - Trend direction.
   - Trend rate and unit.
   - P-value.
   - Significance decision.
   - Confidence interval when available.
   - Number of valid observations.

6. Data information:
   - Dataset source.
   - Variable description.
   - Temporal resolution.
   - Measurement unit.
   - Data coverage.

7. Scientific interpretation:
   - A short plain-language explanation of the result.
   - A warning that statistical association does not establish causation.

Use reusable components and keep the code modular.

Do not create fake analysis results. Connect the interface to the actual data and analysis modules.

Prioritize usability and scientific clarity over decorative design.


## 8. Geographic Visualization

Add a geographic visualization feature to EarthTrend.

Requirements:
- Display the selected study location or region on an interactive map.
- Show the selected coordinates.
- Clearly identify the analyzed variable.
- Make the map consistent with the selected analysis.

If appropriate, use Folium for Streamlit or Leaflet for React.

Do not claim that a single coordinate represents an entire geographic region.

If a spatial dataset is unavailable, show the selected point or region boundary only. Do not fabricate spatial measurements.

Keep this feature optional and ensure the core time-series and statistical analysis remain fully functional without it.



## 9. Testing

Act as an independent scientific software quality engineer.

Audit the EarthTrend application.

Test the full workflow:
1. Variable selection.
2. Geographic selection.
3. Time-period selection.
4. NASA data retrieval.
5. Data preprocessing.
6. Time-series generation.
7. Trend estimation.
8. Statistical significance testing.
9. Result visualization.

Check:
- Incorrect API parameters.
- Invalid units.
- Missing values.
- Duplicate observations.
- Incorrect date parsing.
- Insufficient data.
- Constant time series.
- Statistical implementation errors.
- Misleading significance interpretations.
- UI failures.
- Network errors.
- Security issues.

Use synthetic data only for controlled tests, and clearly identify it as test data.

Compare the expected and actual statistical behavior.

Do not modify the application immediately. First produce an audit report listing:
- Critical issues.
- Major issues.
- Minor issues.
- Recommended fixes.

Then fix issues in priority order and rerun the tests.



## 10. Final Code Review

Perform a final engineering review of EarthTrend before hackathon submission.

Inspect the complete repository.

Check:
- Project organization.
- Code quality.
- Dependency list.
- Installation instructions.
- Configuration files.
- Error handling.
- Scientific correctness.
- Data source attribution.
- API reliability.
- Security.
- Test coverage.
- Reproducibility.

Verify that the application can be installed and started from a clean environment using the README instructions.

Do not remove working features or introduce unnecessary dependencies.

Identify any claims in the application that are not supported by the actual dataset or statistical analysis.

Produce:
1. A final readiness report.
2. A list of remaining blockers.
3. A list of known limitations.
4. Exact startup commands.
5. A submission checklist.




## 11. Presentation Preparation

Act as a NASA Space Apps Challenge presentation coach.

Prepare a compelling presentation for EarthTrend.

The presentation must explain:

1. The environmental problem.
2. Why understanding Earth system trends matters.
3. The problem EarthTrend solves.
4. How users select variables, regions, and time periods.
5. Which NASA datasets are used.
6. How the application creates time series.
7. How statistical significance is tested.
8. A real demonstration of the working application.
9. The practical impact and potential users.
10. Limitations and future development.

Create:
- A slide-by-slide outline.
- Speaker notes.
- A compelling opening statement.
- A clear explanation of the technical architecture.
- A short demo script.
- Possible judge questions and evidence-based answers.

Never invent project achievements, NASA partnerships, data results, or user impact. Clearly separate completed features from planned features.