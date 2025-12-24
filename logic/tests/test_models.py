import pytest
from collections import defaultdict
import numpy as np
import random
from seating_plan.models import validate_cliques, infer_social_graph, generate_similarity_matrix
from seating_plan.tables import BanquetTable
from seating_plan.exceptions import InvalidInput,TableError

def test_validate_cliques():
    cliques = {
        'htb': set(['Anca', 'Bobby', 'Charles','Diana','Tekena','Josh','Melissa']),
        'kcl': set(['Kaolan','Tekena','Josh']),
        'ual': set(['Kate','Mel'])
    }
    valid_cliques, errors = validate_cliques(cliques)
    # Check that the valid cliques are returned correctly
    assert len(valid_cliques) == 3
    assert 'htb' in valid_cliques
    assert 'kcl' in valid_cliques
    assert 'ual' in valid_cliques
    # Check that errors are returned correctly
    assert len(errors) == 0

    #test errors
    cliques['kxc'] = set([])
    cliques['st_saviour'] = set(['Amet','Anca','Judah'])
    cliques['acton'] = set(['Anca','Judah','Amet'])
    valid_cliques, errors = validate_cliques(cliques)
    # Check that the valid cliques are returned correctly
    assert len(valid_cliques) == 4
    assert 'htb' in valid_cliques
    assert 'kcl' in valid_cliques
    assert 'ual' in valid_cliques
    # Check that errors are returned correctly
    assert len(errors) == 2
    assert f"Clique 'kxc' has less than two members: {cliques['kxc']}" in errors
    assert f"Duplicate clique found: 'st_saviour' and 'acton' with members {tuple(sorted(valid_cliques['st_saviour']))}" in errors

data =[
    {'name':'Anca', 'relational_tags':['htb','st_saviour','acton']},
    {'name':'Madison', 'relational_tags':['htb','acton']},
    {'name':'Tekena', 'relational_tags':['htb','kcl']},
    {'name':'Josh', 'relational_tags':['htb','kcl']},
    {'name':'Melissa', 'relational_tags':['htb']},
    {'name':'Kate', 'relational_tags':['ual']},
    {'name':'Mel', 'relational_tags':['ual']},
    {'name':'Julia', 'relational_tags':['cambridge']},
    {'name':'Alex', 'relational_tags':['cambridge','ags']},
    {'name':'Danny', 'relational_tags':['ags','htb']},
    {'name':'Success', 'relational_tags':['ags','cambridge']},
    {'name':'Judah', 'relational_tags':['htb','st_saviour','acton']},
    {'name':'Amet', 'relational_tags':['htb','st_saviour','acton']},
    {'name':'Judd', 'relational_tags':['htb','acton']},
    {'name':'Hannah', 'relational_tags':['htb','acton']}
]
def test_infer_social_graph():
    valid_cliques, errors = infer_social_graph(data, relation_key_word='relational_tags', id_key_word='name')
    # Check that the valid cliques are returned correctly
    assert len(valid_cliques) == 7
    assert 'htb' in valid_cliques
    assert 'kcl' in valid_cliques
    assert 'ual' in valid_cliques
    assert 'st_saviour' in valid_cliques
    assert 'acton' in valid_cliques
    assert 'cambridge' in valid_cliques
    assert 'ags' in valid_cliques
    # Check that errors are returned correctly
    assert len(errors) == 0

def test_generate_similarity_matrix():
    similarity_matrix, id_dict =generate_similarity_matrix(data, relation_key_word='relational_tags', id_key_word='name')
    # Check that the similarity matrix is of the correct size
    assert similarity_matrix.shape == (len(data), len(data))
    # Check that the diagonal is all zeros
    assert np.all(np.diag(similarity_matrix) == 0)
    # Check that the similarity matrix is symmetric
    assert np.all(similarity_matrix == similarity_matrix.T)
    # Check that the id_dict is correct
    assert len(id_dict) == len(data)
    for i, guest in enumerate(data):
        assert id_dict[guest['name']] == i

    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            if set(data[i]['relational_tags']).intersection(set(data[j]['relational_tags'])):
                assert similarity_matrix[i, j] > 0
                assert similarity_matrix[j, i] > 0
            else:
                assert similarity_matrix[i, j] == 0
                assert similarity_matrix[j, i] == 0

