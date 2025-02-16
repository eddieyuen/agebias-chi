from statsmodels.tsa.stattools import adfuller
import pandas as pd
import os
import numpy as np
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.api import VAR

# # Get the current script directory and create paths to the data and output folders
script_dir = os.path.dirname(os.path.abspath(__file__))
data_folder_path = os.path.join(script_dir, '..', '0_data')
pipeline_folder_path = os.path.join(script_dir, '..', '2_pipeline/preprocessed')
pipeline_out_folder_path = os.path.join(script_dir, '..', '2_pipeline/out')
tmp_folder_path = os.path.join(script_dir, '..', '2_pipeline/tmp')
output_folder_path = os.path.join(script_dir, '..', '3_output/results/granger_stationary')
df = pd.read_csv(os.path.join(pipeline_out_folder_path, 'merged.csv'))
if not os.path.exists(output_folder_path):
    os.makedirs(output_folder_path)

df['positive'] = df['old_positive'] - df['young_positive']
df['negative'] = df['old_negative'] - df['young_negative']
df['competent'] = df['old_competent'] - df['young_competent']
df['warm'] = df['old_warm'] - df['young_warm']
df['incompetent'] = df['old_incompetent'] - df['young_incompetent']
df['unwarm'] = df['old_unwarm'] - df['young_unwarm']
df['virtue'] = df['old_virtue'] - df['young_virtue']
df['vice'] = df['old_vice'] - df['young_vice']
df['indicoll'] = df['indi'] - df['coll']
df['tightloose'] = df['tight'] - df['loose']
# df['gdp_per_capita_log'] = np.log(df['GDP.per.capita'])
df = df.set_index('year')
# Interpolate missing values
df = df.interpolate()
dvs = ['positive', 'negative', 'competent', 'warm', 'incompetent', 'unwarm', 'virtue', 'vice']
ivs = ['indi','coll','indicoll', 'tight','loose', 'tightloose']

def calculate_aic(data, maxlag):
    """
    Calculates the AIC values for a VAR model with different numbers of lags.
    :param data: DataFrame with time series data.
    :param maxlag: Maximum number of lags to use.
    :return: List of AIC values.
    """
    model = VAR(data)
    aic_values = []
    for i in range(1, maxlag+1):
        result = model.fit(i)
        aic_values.append(result.aic)
    return aic_values
def make_stationary(series):
    """
    Differencing the time series data until it's stationary.
    """
    result = adfuller(series)
    
    # Assume that our criterion for stationarity is that p < 0.05
    while result[1] > 0.05: 
        series = series.diff().dropna()
        result = adfuller(series)
    return series

def granger_test(df, dvs, ivs, maxlagnum=10):
    """
    Performs a Granger causality test on each combination of dependent and independent variables.
    :param dvs: List of dependent variables.
    :param ivs: List of independent variables.
    :param maxlagnum: Maximum number of lags to use.
    :return: DataFrame with significant results.
    """
    results_dict = {
        "Direction": [],
        "Lag": [],
        "F-statistic": [],
        "p-value": [],
        "AIC": []
    }
    for dv in dvs:
        for iv in ivs:
            # Ensure the series are stationary
            stationary_dv = make_stationary(df[dv])
            stationary_iv = make_stationary(df[iv])
            
            data = pd.concat([stationary_dv, stationary_iv], axis=1)
            data = data.dropna(how='any', axis=0)  # Drops rows with missing values.
            aic_values = calculate_aic(data, maxlagnum)
            gc_res = grangercausalitytests(data, maxlag=maxlagnum, verbose=False)
            for lag, test_results in gc_res.items():
                f_statistic = test_results[0]['ssr_ftest'][0]
                p_value = test_results[0]['ssr_ftest'][1]
                results_dict['Direction'].append(iv + ' -> ' + dv)
                results_dict['Lag'].append(lag)
                results_dict['F-statistic'].append(f_statistic)
                results_dict['p-value'].append(p_value)
                results_dict['AIC'].append(aic_values[lag-1])  # Indexing starts from 0, lag starts from 1.
    results_df = pd.DataFrame(results_dict)
    # Get the row with minimum AIC for each direction
    results_df = results_df.loc[results_df.groupby("Direction")["AIC"].idxmin()]
    # Filter DataFrame to only include significant results
    significant_results_df = results_df[results_df['p-value'] < 0.05]
    return results_df,significant_results_df


iv_predict_dv_all,iv_predict_dv_sig = granger_test(df,dvs,ivs,10)
dv_predict_iv_all,dv_predict_iv_sig = granger_test(df,ivs,dvs,10)

# make sure the output folder exists
if not os.path.exists(output_folder_path):
    os.makedirs(output_folder_path)

# make the result dataframe limited to 2 digits after the decimal point
iv_predict_dv_all = iv_predict_dv_all.round(2)
iv_predict_dv_sig = iv_predict_dv_sig.round(2)
dv_predict_iv_all = dv_predict_iv_all.round(2)
dv_predict_iv_sig = dv_predict_iv_sig.round(2)

iv_predict_dv_all.to_csv(os.path.join(output_folder_path,'iv_predict_dv_simple_all.csv'))
dv_predict_iv_all.to_csv(os.path.join(output_folder_path,'dv_predict_iv_simple_all.csv'))

iv_predict_dv_sig.to_csv(os.path.join(output_folder_path,'iv_predict_dv_simple_sig.csv'))
dv_predict_iv_sig.to_csv(os.path.join(output_folder_path,'dv_predict_iv_simple_sig.csv'))

# Define a function to reverse direction
def reverse_direction(direction):
    terms = direction.split(' -> ')
    return f'{terms[1]} -> {terms[0]}'

# Apply this function to 'Direction' column of the second DataFrame
dv_predict_iv_all['Direction'] = dv_predict_iv_all['Direction'].apply(reverse_direction)

# Set multi-index for both dataframes based on 'Direction' and 'Lag'
iv_predict_dv_sig.set_index(['Direction', 'Lag'], inplace=True)
dv_predict_iv_all.set_index(['Direction', 'Lag'], inplace=True)

# Join iv_predict_dv_sig and dv_predict_iv_all horizontally based on the index
merged_df = iv_predict_dv_sig.join(dv_predict_iv_all, lsuffix='_iv2dv', rsuffix='_dv2iv')

# Reset the index so that 'Direction' and 'Lag' become regular columns again
merged_df.reset_index(inplace=True)
merged_df.to_csv(os.path.join(output_folder_path,'culture_matched.csv'))

iv_predict_dv_all['Direction'] = iv_predict_dv_all['Direction'].apply(reverse_direction)

# Set multi-index for both dataframes based on 'Direction' and 'Lag'
dv_predict_iv_sig.set_index(['Direction', 'Lag'], inplace=True)
iv_predict_dv_all.set_index(['Direction', 'Lag'], inplace=True)

# Join iv_predict_dv_sig and dv_predict_iv_all horizontally based on the index
merged_df = dv_predict_iv_sig.join(iv_predict_dv_all, lsuffix='_iv2dv', rsuffix='_dv2iv')

# Reset the index so that 'Direction' and 'Lag' become regular columns again
merged_df.reset_index(inplace=True)
merged_df.to_csv(os.path.join(output_folder_path,'agebias_matched.csv'))

