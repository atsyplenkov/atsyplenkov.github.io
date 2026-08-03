#import "../../../config.typ": template
#show: template.with(
  title: "Supplementary material to poster presentation @ ANZGG 2024",
  description: "Insights into spatial and temporal changes in suspended sediment yield in the Caucasus Mountains during the Anthropocene",
  date: datetime(year: 2024, month: 2, day: 11),
  page-type: "blog-posting",
  keywords: ("academia",),
  image-path: "/posts/anzgg2024_caucasus-poster_tsyplenkov.png",
  image-alt: "ANZGG 2024 poster about suspended sediment yield in the Caucasus Mountains",
  extra-info: [Categories: academia],
)

= Supplementary material to poster presentation @ ANZGG 2024

#emph[Insights into spatial and temporal changes in suspended sediment yield in the Caucasus Mountains during the Anthropocene]

Hello World!

Here, you can download a PDF version of our poster and find the underlying research. By the way, all references cited on the poster can be found at the bottom of this page: #link("https://elibrary.asabe.org/abstract.asp?aid=20488&t=3")[Harmel et al., 2006]; #link("https://onlinelibrary.wiley.com/doi/abs/10.1002/esp.196")[Steegen and Govers, 2001]; #link("https://linkinghub.elsevier.com/retrieve/pii/S0921818115000752")[Vanmaercke et al., 2015]; and #link("https://pubs.er.usgs.gov/publication/ofr8967")[Williams and Rosgen, 1989]!

#link("/data/posters/anzgg2024_caucasus-poster_tsyplenkov.pdf")[Download Poster (PDF)]

#figure(
  image("../../posts/anzgg2024_caucasus-poster_tsyplenkov.png", width: 80%),
  caption: [ANZGG 2024 poster preview.],
)

== BTW

All papers mentioned here are fully reproducible with a bit of R, magic, and God-save-Excel-databases. You can find the code on #link("https://github.com/atsyplenkov")[my GitHub]!

- #link("https://github.com/atsyplenkov/caucasus-sediment-yield")[Tsyplenkov et al., 2019]
- #link("https://github.com/atsyplenkov/caucasus-sediment-yield2021")[Golosov & Tsyplenkov, 2021]
- #link("https://github.com/atsyplenkov/sediment-caucasus-anthropocene")[Tsyplenkov et al., 2021]

In the current project, together with Prof. Golosov, we estimated the spatio-temporal variability in suspended sediment yield (SSY) and specific water discharge in the Caucasus region. The first two papers coming from this project (#link("https://github.com/atsyplenkov/caucasus-sediment-yield")[Tsyplenkov et al., 2019]; #link("https://github.com/atsyplenkov/caucasus-sediment-yield2021")[Golosov & Tsyplenkov, 2021]) made three primary contributions to the regional sediment yield dynamics: 1) we presented the hitherto largest SSY database for the Caucasus region. We found that Caucasus SSY values are similar in range and average to those of catchments in European alpine climatic zones; 2) despite possible significant uncertainties in the SSY values, analysis of this database indicated clear spatial patterns of SSY in the Caucasus; 3) partial correlation analyses demonstrated that proxies of topography such as height above nearest drainage (HAND) and normalized steepness index (Ksn) tend to be among the most important controlling factors of SSY.

The third paper in this series built on the first by diving deeper into the variability of suspended sediment load in the Anthropocene (#link("https://doi.org/10.1002/hyp.14403")[Tsyplenkov et al., 2021]). We used suspended sediment load (SSL) measurements from 33 gauges in the Terek basin (North Caucasus, Russia) for 1925–2018. However, we found that these observations are subject to uncertainty due to sampling strategy and measurement errors. Using a Monte-Carlo approach, we simulated 10,000 alternative values and calculated 95% confidence intervals. We found that SSL has decreased by 1.17%/year on average. The CUSUM and double mass curve analyses suggested that the transition year was 1988–1994 in most cases. The latter is most likely due to a decrease in glacier and arable lands areas due to climate change and the collapse of the USSR. It is critical for catchments with a high cropland fraction in the foothill belt (\<500 m a.s.l.). Our results were less clear for high-altitude (\>1000 m a.s.l.) catchments. Nonetheless, there are several reasons to expect that high-altitude gauging stations are less exposed to a considerable reduction in suspended sediment load.

== References

- Harmel, D., Cooper, J., Slade, M., Haney, R., and Arnold, G. 2006. "Cumulative uncertainty in measured streamflow and water quality data for small watersheds." *Transactions of the ASABE* 49 (3): 689–701. #link("https://doi.org/10.13031/2013.20488")[doi]
- Steegen, A., and Govers, G. 2001. "Correction factors for estimating suspended sediment export from loess catchments." *Earth Surface Processes and Landforms* 26 (4): 441–449. #link("https://doi.org/10.1002/esp.196")[doi]
- Vanmaercke, M., Poesen, J., Govers, G., and Verstraeten, G. 2015. "Quantifying human impacts on catchment sediment yield: A continental approach." *Global and Planetary Change* 130: 22–36. #link("https://doi.org/10.1016/j.gloplacha.2015.04.001")[doi]
- Williams, G. P., and Rosgen, D. L. 1989. "Measured total sediment loads (suspended loads and bedloads) for 93 United States streams." #link("https://pubs.er.usgs.gov/publication/ofr8967")[Open-File Report]
- Tsyplenkov, A., Vanmaercke, M., and Golosov, V. 2019. "Contemporary suspended sediment yield of Caucasus mountains." *Proceedings of the International Association of Hydrological Sciences* 381: 87–93. #link("https://doi.org/10.5194/piahs-381-87-2019")[doi]
- Golosov, V., and Tsyplenkov, A. 2021. "Factors controlling contemporary suspended sediment yield in the Caucasus region." *Water* 13 (22): 3173. #link("https://doi.org/10.3390/w13223173")[doi]
- Tsyplenkov, A. S., Golosov, V. N., and Belyakova, P. A. 2021. "How did the suspended sediment load change in the North Caucasus during the Anthropocene?" *Hydrological Processes* 35 (10): 1–20. #link("https://doi.org/10.1002/hyp.14403")[doi]

#html.div(
  class: "poster-embed",
  html.elem(
    "iframe",
    attrs: (
      src: "/data/posters/anzgg2024_caucasus-poster_tsyplenkov.pdf#page=1&zoom=20",
      title: "ANZGG 2024 poster",
      width: "100%",
      height: "960",
      loading: "lazy",
    ),
    "",
  ),
)
