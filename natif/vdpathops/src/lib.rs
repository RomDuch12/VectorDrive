//! Opérations de tracés pour VectorDrive : booléens et offset qui conservent
//! les courbes, par `vectorcraft-pathops` (ArtCraft, MIT OR Apache-2.0).
//!
//! Échange avec Python : un tracé est une liste d'opérations `(code, valeurs)`
//! — 0 moveTo (x, y), 1 lineTo (x, y), 2 quadTo (x1, y1, x, y),
//! 3 curveTo (x1, y1, x2, y2, x, y), 4 closePath.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use vectorcraft_geom::kurbo::{BezPath, Cap, Join, PathEl, Point};
use vectorcraft_geom::{FillRule, PathData};
use vectorcraft_pathops as po;

type Op = (u8, Vec<f64>);

fn pt(v: &[f64], i: usize) -> PyResult<Point> {
    match (v.get(i), v.get(i + 1)) {
        (Some(x), Some(y)) if x.is_finite() && y.is_finite() => Ok(Point::new(*x, *y)),
        _ => Err(PyValueError::new_err("coordonnée manquante ou non finie")),
    }
}

fn to_bez(ops: &[Op]) -> PyResult<BezPath> {
    let mut bp = BezPath::new();
    for (code, v) in ops {
        match code {
            0 => bp.move_to(pt(v, 0)?),
            1 => bp.line_to(pt(v, 0)?),
            2 => bp.quad_to(pt(v, 0)?, pt(v, 2)?),
            3 => bp.curve_to(pt(v, 0)?, pt(v, 2)?, pt(v, 4)?),
            4 => bp.close_path(),
            _ => return Err(PyValueError::new_err("opération de tracé inconnue")),
        }
    }
    Ok(bp)
}

fn from_bez(bp: &BezPath) -> Vec<Op> {
    bp.elements()
        .iter()
        .map(|el| match *el {
            PathEl::MoveTo(p) => (0, vec![p.x, p.y]),
            PathEl::LineTo(p) => (1, vec![p.x, p.y]),
            PathEl::QuadTo(a, p) => (2, vec![a.x, a.y, p.x, p.y]),
            PathEl::CurveTo(a, b, p) => (3, vec![a.x, a.y, b.x, b.y, p.x, p.y]),
            PathEl::ClosePath => (4, vec![]),
        })
        .collect()
}

fn rule(evenodd: bool) -> FillRule {
    if evenodd { FillRule::EvenOdd } else { FillRule::NonZero }
}

fn join(name: &str) -> PyResult<Join> {
    match name {
        "round" => Ok(Join::Round),
        "miter" => Ok(Join::Miter),
        "bevel" => Ok(Join::Bevel),
        _ => Err(PyValueError::new_err("jonction inconnue (round, miter, bevel)")),
    }
}

/// Opération booléenne : "union", "intersect", "difference" (a − b), "xor".
/// Le calcul se fait sans le verrou global de Python : un appel qui ne
/// finirait pas peut être abandonné côté Python (délai, repli).
#[pyfunction]
#[pyo3(signature = (a, b, op, evenodd=true, precision=None))]
fn boolean(py: Python<'_>, a: Vec<Op>, b: Vec<Op>, op: &str, evenodd: bool, precision: Option<f64>) -> PyResult<Vec<Op>> {
    let pa = PathData::from_bezpath(&to_bez(&a)?);
    let pb = PathData::from_bezpath(&to_bez(&b)?);
    let bop = match op {
        "union" => po::BoolOp::Union,
        "intersect" => po::BoolOp::Intersect,
        "difference" => po::BoolOp::Difference,
        "xor" => po::BoolOp::Xor,
        _ => return Err(PyValueError::new_err("opération inconnue (union, intersect, difference, xor)")),
    };
    let rl = rule(evenodd);
    let prec = precision.unwrap_or(po::DEFAULT_PRECISION);
    py.allow_threads(move || {
        po::try_boolean(&pa, rl, &pb, rl, bop, prec).map(|r| from_bez(&r.to_bezpath())).map_err(|e| e.to_string())
    })
    .map_err(PyValueError::new_err)
}

/// Décalage d'un tracé (delta > 0 : vers l'extérieur des contours fermés).
#[pyfunction]
#[pyo3(signature = (a, delta, join_name="round", miter_limit=4.0))]
fn offset(py: Python<'_>, a: Vec<Op>, delta: f64, join_name: &str, miter_limit: f64) -> PyResult<Vec<Op>> {
    let pa = PathData::from_bezpath(&to_bez(&a)?);
    let j = join(join_name)?;
    Ok(py.allow_threads(move || from_bez(&po::offset_path(&pa, delta, j, miter_limit).to_bezpath())))
}

/// Contour d'un trait d'épaisseur `width` (tracé ouvert ou fermé).
#[pyfunction]
#[pyo3(signature = (a, width, join_name="round", cap="round", miter_limit=4.0))]
fn outline_stroke(py: Python<'_>, a: Vec<Op>, width: f64, join_name: &str, cap: &str, miter_limit: f64) -> PyResult<Vec<Op>> {
    let pa = PathData::from_bezpath(&to_bez(&a)?);
    let c = match cap {
        "round" => Cap::Round,
        "square" => Cap::Square,
        "butt" => Cap::Butt,
        _ => return Err(PyValueError::new_err("bout inconnu (round, square, butt)")),
    };
    let j = join(join_name)?;
    Ok(py.allow_threads(move || from_bez(&po::outline_stroke(&pa, width, c, j, miter_limit).to_bezpath())))
}

/// Supprime les auto-intersections et les recouvrements (région remplie).
#[pyfunction]
#[pyo3(signature = (a, evenodd=true))]
fn normalize(py: Python<'_>, a: Vec<Op>, evenodd: bool) -> PyResult<Vec<Op>> {
    let pa = PathData::from_bezpath(&to_bez(&a)?);
    let rl = rule(evenodd);
    py.allow_threads(move || po::try_normalize(&pa, rl).map(|r| from_bez(&r.to_bezpath())).map_err(|e| e.to_string()))
        .map_err(PyValueError::new_err)
}

/// Aire de la région remplie.
#[pyfunction]
#[pyo3(signature = (a, evenodd=true))]
fn area(py: Python<'_>, a: Vec<Op>, evenodd: bool) -> PyResult<f64> {
    let pa = PathData::from_bezpath(&to_bez(&a)?);
    let rl = rule(evenodd);
    Ok(py.allow_threads(move || po::area(&pa, rl)))
}

#[pymodule]
fn vdpathops(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Les paniques (bornes de sûreté de linesweeper) deviennent des
    // exceptions Python rattrapées par VectorDrive : pas de message sur la
    // sortie d'erreur.
    std::panic::set_hook(Box::new(|_| {}));
    m.add_function(wrap_pyfunction!(boolean, m)?)?;
    m.add_function(wrap_pyfunction!(offset, m)?)?;
    m.add_function(wrap_pyfunction!(outline_stroke, m)?)?;
    m.add_function(wrap_pyfunction!(normalize, m)?)?;
    m.add_function(wrap_pyfunction!(area, m)?)?;
    Ok(())
}
