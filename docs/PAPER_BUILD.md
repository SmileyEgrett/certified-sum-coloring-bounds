# Manuscript build

The manuscript consists of `paper/paper.tex`, thirteen active table inputs
and `paper/references.bib`. The supplied PDF has 29 pages. Their exact
identities are in `PUBLIC_MANIFEST.sha256`.

The verified environment is TeX Live 2023 on Linux amd64. With Docker
installed, obtain that environment from its public registry by immutable
digest, following Docker's [digest-pull syntax](https://docs.docker.com/reference/cli/docker/image/pull/#pull-an-image-by-digest-immutable-identifier):

```sh
TEX_IMAGE=texlive/texlive@sha256:e9bf6284a0b89606153489f13222e3639300758ff34cfef94ec27c7ff713aae0
docker pull --platform linux/amd64 "$TEX_IMAGE"
docker image inspect "$TEX_IMAGE" --format '{{.Id}}'
```

The image ID must be
`sha256:d02f122905d9b27787ae69d8d5b31020f74d349b72187744332cc481c1a910ff`.
The registry digest identifies the downloadable manifest; the image ID
identifies its configuration. The tag `texlive/texlive:TL2023-historic` is
a descriptive locator, not the identity pin. The image is large; reuse an
authenticated local copy when available.

The source preflight requires Bash, a C++20 compiler, GNU core utilities and
Perl on the host. Set `CHECK_WORK` and `BUILD_WORK` to new absolute paths
outside the checkout, and `BUILD_CPU` to one available logical CPU. The
verified local build used CPU 16:

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
taskset -c "$BUILD_CPU" bash scripts/check_manuscript.sh paper/paper.tex "$CHECK_WORK"
mkdir "$BUILD_WORK"
cp -a "$CHECK_WORK/active-source/." "$BUILD_WORK/"
docker run --rm --pull=never --network none --platform linux/amd64 \
  --cpuset-cpus="$BUILD_CPU" --cpus=1 \
  --user "$(id -u):$(id -g)" \
  -e SOURCE_DATE_EPOCH=1790035200 -e TZ=UTC \
  -e OMP_NUM_THREADS=1 -e OPENBLAS_NUM_THREADS=1 -e MKL_NUM_THREADS=1 \
  --mount "type=bind,source=$BUILD_WORK,target=/work" -w /work \
  "$TEX_IMAGE" \
  bash -c 'latexmk -pdf -pdflatex="pdflatex -no-shell-escape %O %S" -interaction=nonstopmode -halt-on-error -recorder paper.tex'
sha256sum "$BUILD_WORK/paper.pdf"
cmp "$BUILD_WORK/paper.pdf" paper/paper.pdf
```

`SOURCE_DATE_EPOCH=1790035200` and `TZ=UTC` fix generated dates; the author's
display date is set separately in the source. The explicit Docker CPU limits
constrain the container. The local checks verify active-source closure,
24 cited bibliography entries, 80 labels, recorder inputs and a build log
without unresolved references/citations or overfull/underfull boxes.

The public registry manifest was resolved and matched to the installed image.
Build verification uses that local image. This is not a clean-machine
download/install test; the provisioning command above may retrieve large
layers on a new machine.

An arXiv source ZIP contains root `paper.tex`, the thirteen tables,
`references.bib` and the matching freshly generated `paper.bbl`. It excludes
the PDF, auxiliaries and logs. A supplied bbl must match the source because
it can take precedence over the bib in submission processing. Build from a
fresh extraction and compare the resulting PDF and bibliography. Local
TeX success does not establish arXiv acceptance; the author must inspect the
service's processed PDF at submission.
