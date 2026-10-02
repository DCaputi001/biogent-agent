# datasets.R
# The R counterpart of common/datasets.py: turns an opaque dataset ID into a
# path, and refuses anything that is not one.
#
# The reference implementation is common/datasets.py. These two must agree --
# the same ID has to resolve to the same file in the Python and R sandboxes,
# or a cross-check between them compares different data. Change one, change
# the other, and tests/test_dataset_resolution.py checks the patterns match.

UPLOADS_ROOT <- "/data/uploads"
WORKSPACE_ROOT <- "/data/workspace"

# Mirrors DATASET_ID_PATTERN and FILENAME_PATTERN in common/datasets.py.
DATASET_ID_PATTERN <- "^[0-9a-f][0-9a-f-]{7,63}$"
FILENAME_PATTERN <- "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"

validate_dataset_id <- function(dataset_id) {
  if (!is.character(dataset_id) || length(dataset_id) != 1 ||
        !grepl(DATASET_ID_PATTERN, dataset_id)) {
    stop(
      sprintf(
        "'%s' is not a dataset ID. IDs are lowercase hex and hyphens, 8 to 64 characters.",
        as.character(dataset_id)[1]
      ),
      call. = FALSE
    )
  }
  dataset_id
}

validate_filename <- function(filename) {
  if (!is.character(filename) || length(filename) != 1 ||
        !grepl(FILENAME_PATTERN, filename)) {
    stop(
      sprintf(
        "'%s' is not a file name. Names may not contain path separators or start with a dot.",
        as.character(filename)[1]
      ),
      call. = FALSE
    )
  }
  filename
}

upload_root <- function(dataset_id) {
  file.path(UPLOADS_ROOT, validate_dataset_id(dataset_id))
}

workspace_root <- function(dataset_id) {
  file.path(WORKSPACE_ROOT, validate_dataset_id(dataset_id))
}

resolve_upload <- function(dataset_id, filename) {
  root <- upload_root(dataset_id)
  if (!dir.exists(root)) {
    stop(sprintf("no dataset '%s' has been uploaded", dataset_id), call. = FALSE)
  }

  path <- file.path(root, validate_filename(filename))

  # The patterns above should make an escape impossible; this catches the one
  # case they cannot see, which is a symlink inside the uploads volume.
  resolved <- normalizePath(path, mustWork = FALSE)
  if (!startsWith(resolved, normalizePath(UPLOADS_ROOT, mustWork = FALSE))) {
    stop(sprintf("'%s' resolves outside the uploads volume", filename), call. = FALSE)
  }

  if (!file.exists(resolved)) {
    stop(
      sprintf("dataset '%s' has no file '%s'", dataset_id, filename),
      call. = FALSE
    )
  }
  resolved
}
