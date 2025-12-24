import numpy as np
def is_integer_at_least_n(value, n):
    """
    Check if the value is an integer and at least n.
    
    Args:
        value: The value to check.
        n: The minimum acceptable value.
        variable_name: The name of the variable for error messages.
    
    Raises:
        InvalidInput: If the value is not an integer or is less than n.
    """
    if isinstance(value, int) and value >= n:
        return True
    else:
        return False

def is_valid_matrix_id_dict(matrix,id_dict):
    """
    Check that matrix is a 2D numpy array, id_dict is a dictionary and
    the two are compatible.
    """
    if isinstance(matrix, np.ndarray) and matrix.ndim == 2:
        #matrix is a 2D numpy array
        if matrix.shape[0] == matrix.shape[1] and np.all(matrix == matrix.T):
            #matrix is square and symmetric
            if isinstance(id_dict, dict):
                if all(is_integer_at_least_n(v, 0) for v in id_dict.values()):
                    #check that id_dict values are integers and match the matrix indices
                    if len(set(id_dict.values())) == len(id_dict):
                        #check that id_dict values are unique
                        if max(id_dict.values()) < matrix.shape[0]:
                            #check that id_dict values are less than the number of rows/columns in the matrix
                            return True
    return False

def is_in_range(value, min_value, max_value):
    """
    Check if the value is within the specified range (inclusive).
    
    Args:
        value: The value to check.
        min_value: The minimum acceptable value.
        max_value: The maximum acceptable value.
    
    Returns:
        bool: True if value is within the range, False otherwise.
    """
    return min_value <= value <= max_value