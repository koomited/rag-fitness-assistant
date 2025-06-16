
import pandas as pd
import minsearch


def load_index(data_path: str = '../data/data.csv') -> minsearch.Index:
    """
    Load the index from a CSV file.
    Args:
        data_path (str): Path to the CSV file containing the data.
    Returns:
        minsearch.Index: An index object containing the data from the CSV file.
    """
    # Load the data from the CSV file
    if not data_path:
        raise ValueError("data_path must be provided")
 
    df = pd.read_csv('../data/data.csv')
    df.head()
    documents = df.to_dict(orient='records')

    index = minsearch.Index(
        text_fields=['exercise_name', 
                     'type_of_activity', 
                     'type_of_equipment',
                     'body_part',
                    'type', 
                    'muscle_groups_activated', 
                    'instructions'],
        keyword_fields=["ID"]
    )
    index.fit(documents)
    
    return index

