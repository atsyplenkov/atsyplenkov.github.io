#import "../../../config.typ": template
#show: template.with(
  title: "Accessing SoilGrids via {terra}",
  description: "A practical R and terra workflow for downloading, cropping, reprojecting, and parallelizing SoilGrids rasters for a sample area of interest.",
  date: datetime(year: 2022, month: 3, day: 5),
  page-type: "blog-posting",
  keywords: ("R", "soil erosion"),
  image-path: "/blog/2022-03-05-soilgrids-terra/figures/unnamed-chunk-5-1.png",
  image-alt: "SoilGrids raster layer for the North Carolina sample area",
  extra-info: [Categories: R, soil erosion],
)

= Accessing SoilGrids via `{terra}`

After several `QGIS` and `R` packages updates, I cannot download #link("https://www.isric.org/explore/soilgrids")[SoilGrids] with `rgdal` anymore. When I'm trying to run code from #link("https://git.wur.nl/isric/soilgrids/soilgrids.notebooks/-/blob/master/markdown/webdav_from_R.md")[SoilGrids WebDAV tutorial] I am receiving a following error:

#quote(block: true)[
  `ERROR 11: CURL error: SSL certificate problem: unable to get local issuer certificate`
]

I never managed to fix this issue, so I decided to let it go. Here is my approach to downloading cropped and reprojected SoilGrids raster. There was a really great #link("https://rpubs.com/ials2un/soilgrids_webdav")[tutorial] by Ivan Lizarazo on getting several SoilGrids layers using `rgdal`. My approach is mostly based on it.

== 1. Boundary layer

First of all, let's load some boundary layer, i.e., our area of interest (AOI). I will use the default `sf` sample data for North Carolina counties. To reduce the size of AOI, let me select only the first county. The SoilGrids files are stored in Interrupted Goode Homolosine, so I have to reproject our AOI polygon to it.

```r
library(dplyr)
library(sf)

# Load sample data
nc <-  st_read(system.file("shape/nc.shp",
                         package = "sf"),
               quiet = T) %>%
  slice(1)

# Transform to IGH projection
igh <- '+proj=igh +lat_0=0 +lon_0=0 +datum=WGS84 +units=m +no_defs'
nc_igh <- st_transform(nc, igh)
```

== 2. Download urls

Now Let's just copy download urls from previous #link("https://rpubs.com/ials2un/soilgrids_webdav")[tutorials]. And create a link to every other separate `.vrt` file, since we are gonna `purrr::map` them later. I'm interested only in mean topsoil characteristics (i.e. 0-30 cm) right now. So I will download sand, silt, and clay content and soil organic carbon content (soc).

```r
sg_url <- "/vsicurl/https://files.isric.org/soilgrids/latest/data/"
props <- c("sand", "silt", "clay", "soc")
layers <- c("0-5", "5-15", "15-30")

vrt <- paste0(props, "/",
               props, "_",
               rep(layers, 4),
               "cm_mean.vrt")

vrt[1]
```

```text
[1] "sand/sand_0-5cm_mean.vrt"
```

Then, we need to create a list of paths to save. Let's create a directory `soilgrid` where we are going to download our layers.

```r
# Optional
# Check if the directory exists
if (!dir.exists("soilgrid")) {dir.create("soilgrid")}

# Create paths
lfile <- paste0(
  "soilgrid/",
  props, "_",
  rep(layers, 4),
  ".tif")

lfile[1]
```

```text
[1] "soilgrid/sand_0-5.tif"
```

== 3. Download and preprocess function

My general idea is to crop the SoilGrid layer to the bounding box, reproject to my CRS (i.e. CRS of the `nc` layer), download, and then write as `.tif`. However, I want to do this for 12 rasters. Therefore, we need to write a function we are going to apply:

```r
library(terra)

# Function to download and transform soilgrid layers
soilgrids_download <- function(list_vrt, # download url
                               list_lfile, # destination path
                               shape_igh, # AOI shape in IGH proj
                               destproj){ # desired projection

  terra::rast(paste0(sg_url, list_vrt)) %>% # read raster
    terra::crop(ext(vect(shape_igh))) %>%  # crop to bounding box
    terra::project(destproj) %>%  # reproject
    terra::writeRaster(list_lfile,
                       overwrite = T) # Save

}
```

Before running it in the loop, let's try it for the first layer.

```r
soilgrids_download(list_vrt = vrt[1],
                   list_lfile = lfile[1],
                   shape_igh = nc_igh,
                   destproj = st_crs(nc)$proj4string)

rast(lfile[1]) %>%
  plot()
```

#figure(
  image("figures/unnamed-chunk-5-1.png", width: 80%),
  caption: [SoilGrids raster layer downloaded and reprojected for the sample area.],
)

It worked!

== 4. Map download

Next, with the help of `purrr` we can apply this function to all our links. Let's measure elapsed time.

```r
library(purrr)
library(tictoc)

tic()
walk2(vrt,
      lfile,
      ~soilgrids_download(.x, .y,
                          shape_igh = nc_igh,
                          destproj = st_crs(nc)$proj4string))
toc()
```

```text
392.09 sec elapsed
```

Well, almost 2 mins. It is necessary to improve the timing somehow. This process can be run in parallel with `furrr`.

```r
library(furrr)

# Set Parallel
no_cores <- availableCores() - 1
plan(multisession,
     workers = no_cores)

# Download!
tic()
future_walk2(vrt, lfile,
             ~soilgrids_download(.x, .y,
                          shape_igh = nc_igh,
                          destproj = st_crs(nc)$proj4string))
toc()

# Exit parallel
plan(sequential)
```

```text
63.44 sec elapsed
```

Less than 1 minute. As #link("https://www.youtube.com/channel/UCtYLUTtgS3k1Fg4y5tAhLbw")[Josh Starmer] says, "BAM!". Three times faster!

```r
list.files("soilgrid")
```

```text
[1] "clay_0-5.tif" "clay_15-30.tif" "clay_5-15.tif" "sand_0-5.tif"
[5] "sand_15-30.tif" "sand_5-15.tif" "silt_0-5.tif" "silt_15-30.tif"
[9] "silt_5-15.tif" "soc_0-5.tif" "soc_15-30.tif" "soc_5-15.tif"
```

== Citation

```bib
@online{tsyplenkov2022,
  author = {Tsyplenkov, Anatoly},
  title = {Accessing {SoilGrids} via \{Terra\}},
  date = {2022-03-05},
  url = {https://anatolii.nz/blog/2022-03-05-soilgrids-terra/},
  langid = {en}
}
```
