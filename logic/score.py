"""
A series of functions useful for predicting the expected connection score of two people based on data provided.
"""

from collections import defaultdict
import numpy as np
import warnings

def validate_cliques(cliques:dict):
    """
    cliques: dictionary
        Keys are clique tags and values are sets of members.
    Returns: tuple
        A tuple containing:
        - valid_cliques: dictionary of valid cliques
        - errors: list of error messages

    This function validates the cliques based on two conditions:
    1) Each clique should have at least two members.
    2) No two cliques should be identical.
    """
    errors = []
    valid_cliques = {}
    seen_cliques = {}
    error_flag = False
    for tag, members in cliques.items():
        if len(members) < 2:
            errors.append(f"Clique '{tag}' has less than two members: {members}")
            error_flag = True
    
        members_tuple = tuple(sorted(members))
        for seen_tag, seen_members in seen_cliques.items():
            if members_tuple == seen_members:
                errors.append(f"Duplicate clique found: '{seen_tag}' and '{tag}' with members {members_tuple}")
                error_flag = True
        if error_flag:
            error_flag = False
            continue
        seen_cliques[tag]=members_tuple
        valid_cliques[tag] = members
    
    return valid_cliques,errors

def infer_social_graph(data,relation_key_word='relational_tags',id_key_word='id'):
    """
    This function takes in tabular data and infers a social graph
    from the relational tags column. It returns a dictionary
    where keys are unique entities and values are lists of related entities.

    data: list of dictionaries
        Each dictionary represents a row in the table with a 'relational_tags' key.
    Returns: dictionary
        A dictionary representing the social graph.
    """
    cliques = defaultdict(set)

    for guest in data:
        for tag in guest[relation_key_word]:
            cliques[tag].add(guest[id_key_word])
    
    valid_cliques,errors = validate_cliques(cliques)

    return valid_cliques,errors

def generate_similarity_matrix(data, relation_key_word='relational_tags',id_key_word='id'):
    """
    Generate a similarity matrix from guest data
    
    data: list of dictionaries
        Each dictionary represents a row in the table with a 'relational_tags' key.
    Returns: array
        A 2D array representing the estimated similarity between all pairs of guests.
    """
    cliques, errors = infer_social_graph(data, relation_key_word, id_key_word)
    id_dict = {guest[id_key_word]: i for i, guest in enumerate(data)}
    
    
    n = len(data)
    similarity_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            guest_i = data[i]
            guest_j = data[j]
            common_cliques = set(guest_i[relation_key_word]).intersection(set(guest_j[relation_key_word]))
            similarity_score = 0
            for clique in common_cliques:
                if clique in cliques:
                    similarity_score += 1/len(cliques[clique])
        
            similarity_matrix[i][j] = similarity_score
            similarity_matrix[j][i] = similarity_score

    return similarity_matrix,id_dict
