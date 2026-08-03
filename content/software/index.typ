#import "../../config.typ": template
#show: template.with(
  title: "Software",
  description: "Software projects, web apps, editor extensions, and R packages by Anatoly Tsyplenkov, including hydrological tools and research software.",
  page-type: "webpage",
)

= Software

Find complete list at my #link("https://github.com/atsyplenkov")[GitHub] profile.

== Web Apps & VS Code extensions

- #link("https://github.com/atsyplenkov/pastum")[`pastum`] — VS Code extension for inserting text tables as dataframe objects into the editor. *Language:* JavaScript.
- #link("https://github.com/atsyplenkov/detect-chatgpt")[`detect-chatgpt`] — Experimental app for detecting excessive word usage by ChatGPT. *Language:* Python. *Framework:* Streamlit.
- #link("https://github.com/atsyplenkov/bibtex2html")[`bibtex2html`] — App for converting bibliography references to BibTeX format. *Language:* Python. *Framework:* Py-Shiny.
- #link("https://github.com/atsyplenkov/hydrotranslate")[`hydrotranslate`] — Russian-English dictionary of hydrological terms. *Language:* R. *Framework:* R-Shiny.

== Packages

- #link("https://github.com/atsyplenkov/centerline")[`centerline`] #html.elem("img", attrs: (class: "software-badge", src: "https://img.shields.io/github/r-package/v/atsyplenkov/centerline?logo=r&logoColor=276DC3&label=%20&labelColor=white&color=lightgrey.png", alt: "centerline version badge", loading: "lazy"), "") — Centerline extraction and plotting for closed geometries.
- #link("https://github.com/atsyplenkov/tidyhydro")[`tidyhydro`] #html.elem("img", attrs: (class: "software-badge", src: "https://img.shields.io/github/r-package/v/atsyplenkov/tidyhydro?logo=r&logoColor=276DC3&label=%20&labelColor=white&color=lightgrey.png", alt: "tidyhydro version badge", loading: "lazy"), "") — C++ boosted commonly used hydrological metrics for `{tidymodels}` framework.
- #link("https://github.com/atsyplenkov/loadflux")[`loadflux`] #html.elem("img", attrs: (class: "software-badge", src: "https://img.shields.io/github/r-package/v/atsyplenkov/loadflux?logo=r&logoColor=276DC3&label=%20&labelColor=white&color=lightgrey.png", alt: "loadflux version badge", loading: "lazy"), "") — Tools for turbidity and event sediment transport analysis.
- #link("https://github.com/atsyplenkov/rusleR")[`rusleR`] #html.elem("img", attrs: (class: "software-badge", src: "https://img.shields.io/github/r-package/v/atsyplenkov/rusleR?logo=r&logoColor=276DC3&label=%20&labelColor=white&color=lightgrey.png", alt: "rusleR version badge", loading: "lazy"), "") — Soil erosion estimation based on the RUSLE model.
- #link("https://github.com/atsyplenkov/rp5pik")[`rp5pik`] #html.elem("img", attrs: (class: "software-badge", src: "https://img.shields.io/github/r-package/v/atsyplenkov/rp5pik?logo=r&logoColor=276DC3&label=%20&labelColor=white&color=lightgrey.png", alt: "rp5pik version badge", loading: "lazy"), "") — Access meteorological data from pogodaiklimat.ru.
- #link("https://github.com/atsyplenkov/tgme")[`tgme`] #html.elem("img", attrs: (class: "software-badge", src: "https://img.shields.io/github/r-package/v/atsyplenkov/tgme?logo=r&logoColor=276DC3&label=%20&labelColor=white&color=lightgrey.png", alt: "tgme version badge", loading: "lazy"), "") — Send messages to Telegram from R.
- #link("https://github.com/atsyplenkov/HBVr")[`HBVr`] #html.elem("img", attrs: (class: "software-badge", src: "https://img.shields.io/github/r-package/v/atsyplenkov/HBVr?logo=r&logoColor=276DC3&label=%20&labelColor=white&color=lightgrey.png", alt: "HBVr version badge", loading: "lazy"), "") — Access HBV model parameters dataset from Beck et al. (2021).

#html.elem(
  "section",
  attrs: (id: "apps", class: "software-apps"),
  {
    html.elem("h3", [Apps])
    html.p([
      Below is a list of a #link("https://shiny.rstudio.com/")[Shiny] web apps developed and curated by me. Most of them are running on my own shiny server — `atsyplenkov.pp.ru`.
    ])
    html.div(
      class: "software-grid",
      {
        html.article(
          class: "software-card",
          {
            html.elem("img", attrs: (src: "/data/logos/hydrotranslate.png", alt: "Hydrotranslate logo", loading: "lazy"), "")
            html.div(
              class: "software-card-body",
              {
                html.elem("h4", [Hydrotranslate])
                html.p([English-Russian and Russian-English translator of hydrological terms and definitions. An open-source project run by me, DScn. Sergey Chalov and Dr. Vsevolod Moreydo.])
                html.p([
                  #link("https://hydrotranslate.ru/")[Launch App] ·
                  #link("https://github.com/atsyplenkov/hydrotranslate")[Github]
                ])
              },
            )
          },
        )
        html.article(
          class: "software-card",
          {
            html.elem("img", attrs: (src: "/data/logos/zepter.png", alt: "Zepter logo", loading: "lazy"), "")
            html.div(
              class: "software-card-body",
              {
                html.elem("h4", [Zepter])
                html.p([
                  The `Zepter` app can ease the currency conversion within the #link("https://mironline.ru/support/list/kursy_mir/")[MIR payment system]. Since many banks using their own exchange rate, the calculation of the final rate can be struggling. This app is parsing `CBR`, `MIR` and `Zepter Bank` websites to get the up-to-date exchange rates and summarise them in a neat table.
                ])
                html.p([
                  #link("https://atsyplenkov.pp.ru/shiny/zepter")[Launch App] ·
                  #link("https://github.com/atsyplenkov/shiny-server/tree/master/zepter")[Github]
                ])
              },
            )
          },
        )
        html.article(
          class: "software-card",
          {
            html.elem("img", attrs: (src: "/data/logos/rewriter.png", alt: "Rewriter logo", loading: "lazy"), "")
            html.div(
              class: "software-card-body",
              {
                html.elem("h4", [Rewriter])
                html.p([
                  This is a very simple shiny app aimed on paraphrasing *Russian* texts. It is using `Rewriter` by Sber model's #link("https://sbercloud.ru/ru/datahub/rugpt3family/demo-rewrite")[API]. From news and fiction to social media posts, the `Rewriter` is able to rewrite any text with the same meaning, regardless of length or format.
                ])
                html.p([
                  #link("https://atsyplenkov.pp.ru/shiny/sber")[Launch App] ·
                  #link("https://github.com/atsyplenkov/shiny-server/tree/master/sber")[Github]
                ])
              },
            )
          },
        )
      },
    )
  },
)
