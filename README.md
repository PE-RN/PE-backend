
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

<h4 style="color: yellow;"> Não realizar commit's diretos nas branch's de release e main. Sempre realizar um Pull Request seguindo seguinte padrão:<br/><br/>
Criação de branchs<br/><br>
    - Branch's devem ser criadas pela ferramenta de criação no jira<br/><br/>
    - Toda branch deve ser criada a partir da release atual<br/><br/>
    - O nome da branch deve seguir o padrão da criação pelo jira IdTask-Nome-Task<br/><br/>
Commits em branchs<br/><br>
    - Deve seguir o padrão "tipo(participante): commit message"<br/><br/>
Merge em release e main<br/><br>
    - Apenas as releases podem ser mergeadas dentro da main<br/><br/>
    - Branchs de desenvolvimento devem ser mergeadas na release<br/><br/>
    - Antes de mergear uma branch na release faça o rebase com o commit mais recente da release<br/><br/>
    - Sempre enviar a tarefa para review após abrir o pull request na release<br/><br/>
    - É necessário um approve de outro dev para realizar o merge<br/><br/>
    - Para mergear selecione a opção de squash and merge<br/><br/>
    - Delete a branch após mergear o código<br/><br/>
    - No final da sprint a release será mergeada na main<br/><br/>



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


