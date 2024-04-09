
# Back-end 

<img src="https://raw.githubusercontent.com/MicaelliMedeiros/micaellimedeiros/master/image/computer-illustration.png" alt="Exemplo imagem">

> Repositório back-end do projeto PE que pretende desenvolver uma API para fornercer os dados processados necessários.

### 📀 Recomendações e avisos

Recomendados o uso do ambiente virtual do miniconda para gerenciamento de ambiente, você pode encontrar a instalação e cheatsheet nos links abaixo:
- [instalação](https://docs.anaconda.com/free/miniconda/#quick-command-line-install)
- [cheatsheet](https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf)
- Guia simples para uso em Linux:
```
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm -rf ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init bash
~/miniconda3/bin/conda init zsh
```
Agora reinicie a janela do terminal e execute

```
conda create --name atlas python=3.11
conda activate atlas
```
Pronto você criou uma env e estar pronto para começar 😄😄😄😄

<h4 style="color: yellow;"> Lembre-se sempre de estar numa env antes de iniciar o processo de instalação para nao acabar colocando no arquivo de requerimentos, pacotes sem necessidade, e se atente também a toda vez que utilizar um novo pacote no projeto, atualizar a lista de depedências  com os comando</h4>
<h5 style="color: yellow;"> Para Linux</h5>

```
pip freeze | grep -vE "file:///" > requirements.txt
```

<h5 style="color: yellow;"> Para Windows</h5>

```
pip freeze | findstr /v "file:///" > requirements.txt"
```

<h5 style="color: yellow;"> Isso joga todos os pacotes e suas versões usadas atraves do "pip freeze" num arquivo txt usando o operador de alteração de saída ">"
e eliminano dessa inserção todos os pacotes com path "file:///" que são os default da env do miniconda. </h5>

<h4 style="color: yellow;"> Não realizar commit's diretos nas branch's de development,main sempre realizar um Pull Request seguindo seguinte padrão:<br/><br/>
    - Branch's de task's de melhorias do jira PE-2845-feature sendo 2845 o número da task do jira.<br/><br/>
    - Brach's de task's de correção de erro do jira PE-2845-bugfix sendo 2845 o número da task do jira.<br/><br/>
    - Padrão de commit: PE-2314: Realizar configuração de modelo onde 2314 é o número da branch atual e apos o : colocar um verbo no infinitivo + resto da mensagem


</h4>

## 🚀 Instalando  o projeto

Apos inicializar sua env, para instalar siga essas etapas:

Linux e Windows:


```
pip install -r requirements.txt
```


## ☕ Usando 

Para usar siga estas etapas:

```
uvicorn main:app --reload
```


