# The methodology 3.3 binomial GLMM on the full answer table, and what depends on it: the logit
# contrast per model, the Wald test of equal contrasts, the item:condition SD with its profile
# interval, the LRT and the held-out log-likelihood (Laplace, whole projects or repositories held
# out) against the model without item:condition, the item-logit correlations against a
# one-ability reference, the common-slope check, the probit refit and the item flags. Inputs
# come from `scripts/analysis.py prep`.
#
#   OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 mamba run -n codeimg-glmm Rscript \
#     analysis/glmm_main.R [--bench coderujb|deveval] [--workers 5] [--in scratch/analysis]
#     [--out results/analysis] [--folds 10] [--sims 1000]
#
# Writes <out>/glmm.json, <out>/glmm_item_flags.csv and <out>/glmm_item_model.csv. Fit times go
# to stderr only, so a rerun writes identical files. The script stops, writing nothing, when a
# main fit does not converge or one of the built-in checks fails.
suppressPackageStartupMessages({
  library(glmmTMB)
  library(parallel)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
opt <- function(name, default) {
  i <- match(paste0("--", name), args)
  if (is.na(i)) default else args[i + 1]
}
script_dir <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE))))
root <- dirname(script_dir)
path <- function(p) if (startsWith(p, "/")) p else file.path(root, p)

benches <- if (is.na(match("--bench", args))) c("coderujb", "deveval") else opt("bench", NULL)
workers <- as.integer(opt("workers", 5))
in_dir <- path(opt("in", "scratch/analysis"))
out_dir <- path(opt("out", "results/analysis"))
n_folds <- as.integer(opt("folds", 10))
n_sims <- as.integer(opt("sims", 1000))

SEED_FOLDS <- 20261115
SEED_SIMS <- 20261117
LEVEL <- 0.95
FORMULA <- cbind(k, n - k) ~ model * condition + (1 | item) + (1 | item:model) +
  (1 | item:condition) + (1 | project) + (1 | project:condition) + (1 | cell)
REDUCED <- update(FORMULA, . ~ . - (1 | item:condition))
TERMS <- c("item", "item:model", "item:condition", "project", "project:condition", "cell")
TOL_EXACT <- 1e-8
TOL_REFIT <- 1e-3
TOL_LAPLACE <- 1e-4

log_line <- function(...) cat(sprintf(...), "\n", file = stderr(), sep = "")

read_answers <- function(b) {
  a <- read.csv(file.path(in_dir, paste0(b, "_answers.csv")), stringsAsFactors = FALSE,
                colClasses = c(item = "character", project = "character"))
  a$model <- factor(a$model, levels = unique(a$model))
  a$condition <- factor(a$condition, levels = unique(a$condition))
  stopifnot(levels(a$condition)[1] == "text")
  a
}

cells_of <- function(a) {
  key <- paste(as.integer(a$model), a$item, as.integer(a$condition), sep = "\r")
  first <- !duplicated(key)
  d <- a[first, c("model", "item", "project", "condition")]
  d$k <- as.vector(tapply(a$passed, factor(key, levels = key[first]), sum))
  d$n <- as.vector(table(factor(key, levels = key[first])))
  d$cell <- factor(seq_len(nrow(d)))
  rownames(d) <- NULL
  d
}

capture <- function(expr) {
  msgs <- character()
  val <- withCallingHandlers(
    tryCatch(expr, error = function(e) structure(conditionMessage(e), class = "fit_error")),
    warning = function(w) {
      msgs <<- c(msgs, conditionMessage(w))
      invokeRestart("muffleWarning")
    })
  list(value = val, warnings = unique(msgs))
}

# converged: no error, no warning, optimizer code 0 and a positive-definite Hessian
fit_model <- function(formula, d, label, link = "logit") {
  secs <- system.time(res <- capture(glmmTMB(formula, data = d,
                                             family = binomial(link = link))))[["elapsed"]]
  fit <- res$value
  ok <- !inherits(fit, "fit_error") && length(res$warnings) == 0 &&
    identical(as.integer(fit$fit$convergence), 0L) && isTRUE(fit$sdr$pdHess)
  log_line("%s: %.1f s, converged %s", label, secs, ok)
  list(fit = if (inherits(fit, "fit_error")) NULL else fit, ok = ok,
       problem = if (ok) NA_character_ else
         paste(c(if (inherits(fit, "fit_error")) unclass(fit), res$warnings,
                 if (!inherits(fit, "fit_error") && !isTRUE(fit$sdr$pdHess)) "Hessian not pdHess"),
               collapse = "; "))
}

main_fit <- function(formula, d, label, link = "logit") {
  f <- fit_model(formula, d, label, link)
  if (!f$ok) stop(sprintf("%s did not converge (%s); not switching optimizer without the user",
                          label, f$problem))
  f$fit
}

sds_of <- function(fit) {
  s <- sapply(VarCorr(fit)$cond, function(m) attr(m, "stddev")[[1]])
  s[TERMS]
}

grid_of <- function(d) {
  g <- expand.grid(model = levels(d$model), condition = levels(d$condition),
                   stringsAsFactors = FALSE)
  g$model <- factor(g$model, levels = levels(d$model))
  g$condition <- factor(g$condition, levels = levels(d$condition))
  g
}

fixed_eta <- function(fit, g) {
  X <- model.matrix(~ model * condition, g)
  beta <- fixef(fit)$cond
  drop(X %*% beta[colnames(X)])
}

# rows: one contrast vector per model, mean over sizes of eta(m, s) - eta(m, text)
contrast_matrix <- function(fit, g) {
  X <- model.matrix(~ model * condition, g)
  beta <- fixef(fit)$cond
  L <- t(sapply(levels(g$model), function(m) {
    s <- g$model == m
    colMeans(X[s & g$condition != "text", , drop = FALSE]) - X[s & g$condition == "text", ]
  }))
  L[, names(beta), drop = FALSE]
}

contrasts_of <- function(fit, g) {
  L <- contrast_matrix(fit, g)
  beta <- fixef(fit)$cond
  V <- vcov(fit)$cond[names(beta), names(beta)]
  est <- drop(L %*% beta)
  se <- sqrt(diag(L %*% V %*% t(L)))
  q <- qnorm(0.5 + LEVEL / 2)
  list(L = L, V = V, beta = beta,
       table = data.frame(model = rownames(L), est = est, se = se, lo = est - q * se,
                          hi = est + q * se, stringsAsFactors = FALSE, row.names = NULL))
}

wald_equal <- function(cc, ref) {
  M <- nrow(cc$L)
  others <- setdiff(seq_len(M), ref)
  D <- cc$L[others, , drop = FALSE] - matrix(cc$L[ref, ], length(others), ncol(cc$L), byrow = TRUE)
  db <- D %*% cc$beta
  stat <- drop(t(db) %*% solve(D %*% cc$V %*% t(D), db))
  list(stat = stat, df = M - 1, p = pchisq(stat, M - 1, lower.tail = FALSE))
}

# (b): a refit coded so that the size-averaged image effect of model m is one coefficient
refit_contrast <- function(d, m) {
  d2 <- d
  d2$model <- relevel(d2$model, ref = m)
  C <- rbind(text = c(0, 0, 0), c(1, 1, 0), c(1, 0, 1), c(1, -1, -1))
  stopifnot(nlevels(d2$condition) == 4)
  rownames(C) <- levels(d2$condition)
  contrasts(d2$condition) <- C
  fit <- main_fit(FORMULA, d2, sprintf("refit with %s as reference", m))
  b <- fixef(fit)$cond
  V <- vcov(fit)$cond
  list(est = b[["condition1"]], se = sqrt(V["condition1", "condition1"]))
}

# the profile is on the log-SD scale; confint only takes this parameter by its position (the
# fixed effects first, then one theta per term in formula order)
profile_sd <- function(fit) {
  k <- which(TERMS == "item:condition")
  est <- sds_of(fit)[["item:condition"]]
  ci <- tryCatch({
    pos <- sum(names(fit$fit$par) == "beta") + k
    r <- suppressWarnings(confint(fit, parm = pos, method = "profile", level = LEVEL))
    if (!all(is.finite(r[1, 1:2]))) stop("non-finite profile bound")
    list(lo = exp(r[1, 1]), hi = exp(r[1, 2]), method = "profile")
  }, error = function(e) NULL)
  if (is.null(ci)) {
    theta <- fit$fit$par[names(fit$fit$par) == "theta"][k]
    se <- sqrt(diag(fit$sdr$cov.fixed)[names(fit$sdr$par.fixed) == "theta"][k])
    q <- qnorm(0.5 + LEVEL / 2)
    ci <- list(lo = exp(theta - q * se), hi = exp(theta + q * se), method = "wald_log_sd")
  }
  c(list(est = est), ci)
}


cell_eta <- function(fit, g, dc) {
  eta <- fixed_eta(fit, g)
  eta[match(paste(dc$model, dc$condition), paste(g$model, g$condition))]
}

# the Laplace log-likelihood of d at the parameters of fit, nothing re-estimated; clusters are
# independent, so on several held-out clusters it is the sum of theirs
laplace_loglik <- function(fit, formula, d) {
  d$cell <- factor(seq_len(nrow(d)))
  beta <- fixef(fit)$cond
  theta <- unname(fit$fit$par[names(fit$fit$par) == "theta"])
  res <- capture(glmmTMB(formula, data = d, family = binomial,
                         start = list(beta = unname(beta), theta = theta),
                         map = list(beta = factor(rep(NA, length(beta))),
                                    theta = factor(rep(NA, length(theta))))))
  if (inherits(res$value, "fit_error")) stop(unclass(res$value))
  as.numeric(logLik(res$value))
}

heldout_fold <- function(f, d, folds) {
  test <- names(folds)[folds == f]
  train <- d[!d$project %in% test, ]
  train$cell <- factor(seq_len(nrow(train)))
  full <- fit_model(FORMULA, train, sprintf("fold %d full", f))
  red <- fit_model(REDUCED, train, sprintf("fold %d reduced", f))
  out <- list(fold = f, clusters = length(test), converged = full$ok && red$ok,
              full = NA_real_, reduced = NA_real_)
  if (!out$converged) return(out)
  held <- d[d$project %in% test, ]
  out$full <- laplace_loglik(full$fit, FORMULA, held)
  out$reduced <- laplace_loglik(red$fit, REDUCED, held)
  out
}

heldout <- function(d) {
  projects <- sort(unique(d$project))
  set.seed(SEED_FOLDS)
  folds <- setNames(sample(rep(seq_len(n_folds), length.out = length(projects))), projects)
  res <- mclapply(seq_len(n_folds), heldout_fold, d = d, folds = folds,
                  mc.cores = workers, mc.preschedule = FALSE)
  bad <- sapply(res, function(r) is.null(r) || inherits(r, "try-error"))
  if (any(bad)) stop(sprintf("held-out folds %s died", paste(which(bad), collapse = ", ")))
  rows <- do.call(rbind, lapply(res, as.data.frame))
  ok <- rows$converged
  diff <- rows$full[ok] - rows$reduced[ok]
  list(folds = rows, full = sum(rows$full[ok]), reduced = sum(rows$reduced[ok]),
       diff = sum(diff), se = if (sum(ok) > 1) sd(diff) * sqrt(sum(ok)) else NA_real_,
       partial = !all(ok), integration = "laplace")
}

# (d): evaluated on the data it was fitted to, laplace_loglik gives the fit's own logLik
check_laplace <- function(d, fit) {
  got <- laplace_loglik(fit, FORMULA, d)
  want <- as.numeric(logLik(fit))
  list(laplace = got, fit = want, ok = abs(got - want) < TOL_LAPLACE)
}


emp_logit <- function(k, n) log((k + 0.5) / (n - k + 0.5))

# per item and condition, passes summed over models (and runs), as a matrix items x conditions
item_logits <- function(d) {
  k <- tapply(d$k, list(d$item, d$condition), sum)
  n <- tapply(d$n, list(d$item, d$condition), sum)
  emp_logit(k, n)
}

PAIRS <- function(conds) {
  sizes <- conds[-1]
  rbind(cbind("text", sizes), t(combn(sizes, 2)))
}

correlations <- function(lg, pairs) {
  out <- list()
  for (method in c("pearson", "spearman")) {
    r <- apply(pairs, 1, function(p) cor(lg[, p[1]], lg[, p[2]], method = method))
    text <- pairs[, 1] == "text"
    out[[method]] <- c(setNames(r, paste(pairs[, 1], pairs[, 2], sep = "~")),
                       C = mean(r[!text]) - mean(r[text]))
  }
  out
}

simulate_cells <- function(d, eta0, sds) {
  draw <- function(key, sd) rnorm(nlevels(key), 0, sd)[as.integer(key)]
  key <- function(...) factor(paste(..., sep = "\r"))
  eta <- eta0 + draw(factor(d$item), sds[["item"]]) +
    draw(key(d$item, d$model), sds[["item:model"]]) +
    draw(factor(d$project), sds[["project"]]) +
    draw(key(d$project, d$condition), sds[["project:condition"]]) +
    draw(d$cell, sds[["cell"]])
  d$k <- rbinom(nrow(d), d$n, plogis(eta))
  d
}

q1 <- function(x, p) unname(quantile(x, p, type = 1))

one_ability <- function(d, fit, g) {
  conds <- levels(d$condition)
  pairs <- PAIRS(conds)
  observed <- correlations(item_logits(d), pairs)
  eta0 <- cell_eta(fit, g, d)
  sds <- sds_of(fit)
  set.seed(SEED_SIMS)
  sims <- lapply(seq_len(n_sims), function(r) correlations(item_logits(simulate_cells(d, eta0, sds)), pairs))
  lapply(setNames(names(observed), names(observed)), function(method) {
    obs <- observed[[method]]
    sim <- do.call(rbind, lapply(sims, `[[`, method))
    lapply(setNames(names(obs), names(obs)), function(k) {
      list(observed = obs[[k]], lo = q1(sim[, k], 0.025), hi = q1(sim[, k], 0.975),
           percentile = mean(sim[, k] <= obs[[k]]))
    })
  })
}

# image logit from run 1 regressed on text logit from run 0, per size, both summed over models
common_slope <- function(a) {
  conds <- levels(a$condition)
  lg <- function(cond, run) {
    s <- a[a$condition == cond & a$run == run, ]
    emp_logit(tapply(s$passed, s$item, sum), tapply(s$passed, s$item, length))
  }
  t0 <- lg("text", 0)
  t1 <- lg("text", 1)[names(t0)]
  if (anyNA(t1)) stop("the common slope needs a run 1 for every item")
  r <- cor(t0, t1)
  lapply(setNames(conds[-1], conds[-1]), function(s) {
    y <- lg(s, 1)[names(t0)]
    if (anyNA(y)) stop(sprintf("the common slope needs a run 1 of %s for every item", s))
    m <- lm(y ~ t0)
    slope <- unname(coef(m)[2])
    list(slope = slope, r2 = summary(m)$r.squared, text_run_correlation = r,
         corrected = slope / r)
  })
}


split_key <- function(keys, levels_) {
  suffix <- sapply(keys, function(k) levels_[endsWith(k, paste0(":", levels_))][1])
  data.frame(item = substr(keys, 1, nchar(keys) - nchar(suffix) - 1), level = suffix,
             stringsAsFactors = FALSE, row.names = NULL)
}

item_flags <- function(b, fit, d) {
  re <- ranef(fit, condVar = TRUE)$cond
  ic <- re[["item:condition"]]
  sd <- sqrt(attr(ic, "condVar")[1, 1, ])
  key <- split_key(rownames(ic), levels(d$condition))
  z <- ic[, 1] / sd
  p <- 2 * pnorm(-abs(z))
  flags <- data.frame(benchmark = b, item = key$item, condition = key$level, mode = ic[, 1],
                      sd = sd, z = z, p = p, p_bh = p.adjust(p, "BH"), stringsAsFactors = FALSE)
  flags <- flags[order(flags$item, match(flags$condition, levels(d$condition))), ]
  im <- re[["item:model"]]
  key <- split_key(rownames(im), levels(d$model))
  modes <- data.frame(benchmark = b, item = key$item, model = key$level, mode = im[, 1],
                      stringsAsFactors = FALSE)
  modes <- modes[order(match(modes$model, levels(d$model)), modes$item), ]
  list(flags = flags, modes = modes,
       summary = list(n = nrow(flags), bh_flagged = sum(flags$p_bh < 0.05),
                      raw_ci_excludes_zero = sum(flags$p < 1 - LEVEL),
                      bh_flagged_loss = sum(flags$p_bh < 0.05 & flags$mode < 0)))
}


run_bench <- function(b) {
  a <- read_answers(b)
  d <- cells_of(a)
  g <- grid_of(d)
  fit <- main_fit(FORMULA, d, sprintf("%s full", b))
  cc <- contrasts_of(fit, g)
  M <- nrow(cc$L)

  # (a) the contrast is the mean of the population-level predicted differences
  nd <- g
  nd$item <- NA
  nd$project <- NA
  nd$cell <- NA
  pr <- predict(fit, newdata = nd, re.form = NA, type = "link", allow.new.levels = TRUE)
  via_predict <- sapply(levels(g$model), function(m) {
    s <- g$model == m
    mean(pr[s & g$condition != "text"]) - pr[s & g$condition == "text"]
  })
  check_a <- max(abs(via_predict - cc$table$est))
  # (b) the delta-method SE of the last model is the SE of a refit coefficient
  last <- levels(d$model)[M]
  rb <- refit_contrast(d, last)
  check_b <- c(est = abs(rb$est - cc$table$est[M]), se = abs(rb$se / cc$table$se[M] - 1))
  # (c) the Wald statistic does not depend on the reference model
  w1 <- wald_equal(cc, 1)
  wM <- wald_equal(cc, M)
  check_c <- abs(w1$stat - wM$stat) / w1$stat
  check_d <- check_laplace(d, fit)
  checks <- list(
    a = list(max_abs_diff = check_a, ok = check_a < TOL_EXACT),
    b = list(model = last, est_abs_diff = check_b[["est"]], se_rel_diff = check_b[["se"]],
             ok = all(check_b < TOL_REFIT)),
    c = list(rel_diff = check_c, ok = check_c < TOL_EXACT),
    d = check_d)
  failed <- names(checks)[!sapply(checks, `[[`, "ok")]
  if (length(failed)) stop(sprintf("%s: check(s) %s failed", b, paste(failed, collapse = ", ")))

  red <- main_fit(REDUCED, d, sprintf("%s without item:condition", b))
  lrt <- 2 * (as.numeric(logLik(fit)) - as.numeric(logLik(red)))
  probit <- main_fit(FORMULA, d, sprintf("%s probit", b), link = "probit")
  sd_logit <- sds_of(fit)
  sd_probit <- sds_of(probit)
  t0 <- Sys.time()
  prof <- profile_sd(fit)
  log_line("%s profile: %.1f s (%s)", b, as.numeric(Sys.time() - t0, units = "secs"), prof$method)
  t0 <- Sys.time()
  ho <- heldout(d)
  log_line("%s held-out: %.1f s", b, as.numeric(Sys.time() - t0, units = "secs"))
  t0 <- Sys.time()
  oa <- one_ability(d, fit, g)
  log_line("%s simulations: %.1f s", b, as.numeric(Sys.time() - t0, units = "secs"))
  fl <- item_flags(b, fit, d)

  list(
    json = list(
      n_cells = nrow(d), n_items = length(unique(d$item)),
      n_clusters = length(unique(d$project)), models = levels(d$model),
      conditions = levels(d$condition), loglik = as.numeric(logLik(fit)),
      sd = as.list(sd_logit),
      contrast = cc$table,
      wald = list(stat = w1$stat, df = w1$df, p = w1$p),
      item_condition_sd = prof,
      lrt = list(stat = lrt, df = 1, p = 0.5 * pchisq(lrt, 1, lower.tail = FALSE)),
      heldout = list(folds = ho$folds, full = ho$full, reduced = ho$reduced, diff = ho$diff,
                     se = ho$se, partial = ho$partial, integration = ho$integration),
      correlation = oa,
      common_slope = common_slope(a),
      probit = list(sd = as.list(sd_probit),
                    ratio_logit = sd_logit[["item:condition"]] / sd_logit[["item"]],
                    ratio_probit = sd_probit[["item:condition"]] / sd_probit[["item"]]),
      item_flags = fl$summary,
      checks = checks),
    flags = fl$flags, modes = fl$modes)
}

rnd <- function(x, key = "") {
  if (is.list(x) && !is.data.frame(x)) {
    return(setNames(lapply(names(x), function(k) rnd(x[[k]], k)), names(x)))
  }
  if (is.data.frame(x)) {
    for (k in names(x)) x[[k]] <- rnd(x[[k]], k)
    return(x)
  }
  if (is.numeric(x) && !is.integer(x)) {
    return(if (key %in% c("p", "p_bh")) signif(x, 3) else round(x, 6))
  }
  x
}

results <- lapply(setNames(benches, benches), run_bench)
out <- list(settings = list(formula = paste(deparse(FORMULA, width.cutoff = 500), collapse = ""),
                            level = LEVEL, folds = n_folds, sims = n_sims,
                            seeds = list(folds = SEED_FOLDS, sims = SEED_SIMS),
                            glmmTMB = as.character(packageVersion("glmmTMB")),
                            R = paste(R.version$major, R.version$minor, sep = ".")),
            benchmarks = lapply(results, `[[`, "json"))
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
writeLines(toJSON(rnd(out), auto_unbox = TRUE, pretty = TRUE, digits = NA, dataframe = "rows",
                  na = "null"),
           file.path(out_dir, "glmm.json"))
write.csv(rnd(do.call(rbind, lapply(results, `[[`, "flags"))),
          file.path(out_dir, "glmm_item_flags.csv"), row.names = FALSE)
write.csv(rnd(do.call(rbind, lapply(results, `[[`, "modes"))),
          file.path(out_dir, "glmm_item_model.csv"), row.names = FALSE)
log_line("wrote %s", out_dir)
