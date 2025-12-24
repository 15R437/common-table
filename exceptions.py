class AppError(Exception):
    """Base class for exceptions in this app"""
    pass

#### TableError ####
class TableError(AppError):
    pass

class InvalidInput(AppError):
    pass

#### OptimiserError ####
class OptimiserError(AppError):
    pass

#### ModelError ####
class ModelError(AppError):
    pass


