"""Exceções específicas das etapas do fluxo de otimização."""


class ErroCarregamentoDados(ValueError):
    """Indica falha de leitura, formato ou validação dos dados de entrada."""


class ErroConstrucaoModelo(ValueError):
    """Indica falha ao validar os parâmetros ou construir o modelo Pyomo."""
