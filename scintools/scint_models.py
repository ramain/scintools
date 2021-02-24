#!/usr/bin/env python

"""
models.py
----------------------------------
Scintillation models

A library of scintillation models to use with lmfit

    Each model has at least inputs:
        params
        xdata
        ydata
        weights

    And output:
        residuals = (ydata - model) * weights

    Some functions use additional inputs
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import numpy as np
from scipy.interpolate import interp2d
import matplotlib.pyplot as plt


def tau_acf_model(params, xdata, ydata, weights):
    """
    Fit 1D function to cut through ACF for scintillation timescale.
    Exponent is 5/3 for Kolmogorov turbulence.
        amp = Amplitude
        tau = timescale at 1/e
        alpha = index of exponential function. 2 is Gaussian, 5/3 is Kolmogorov
        wn = white noise spike in ACF cut
    """

    if weights is None:
        weights = np.ones(np.shape(ydata))

    parvals = params.valuesdict()

    amp = parvals['amp']
    tau = parvals['tau']
    alpha = parvals['alpha']
    wn = parvals['wn']

    model = amp*np.exp(-np.divide(xdata, tau)**(alpha))
    model[0] = model[0] + wn  # add white noise spike
    # Multiply by triangle function
    model = np.multiply(model, 1-np.divide(xdata, max(xdata)))

    return (ydata - model) * weights


def dnu_acf_model(params, xdata, ydata, weights):
    """
    Fit 1D function to cut through ACF for decorrelation bandwidth.
    Default function has is exponential with dnu measured at half power
        amp = Amplitude
        dnu = bandwidth at 1/2 power
        wn = white noise spike in ACF cut
    """

    if weights is None:
        weights = np.ones(np.shape(ydata))

    parvals = params.valuesdict()

    amp = parvals['amp']
    dnu = parvals['dnu']
    wn = parvals['wn']

    model = amp*np.exp(-np.divide(xdata, dnu/np.log(2)))
    model[0] = model[0] + wn  # add white noise spike
    # Multiply by triangle function
    model = np.multiply(model, 1-np.divide(xdata, max(xdata)))

    return (ydata - model) * weights


def scint_acf_model(params, xdata, ydata, weights):
    """
    Fit both tau (tau_acf_model) and dnu (dnu_acf_model) simultaneously
    """

    if weights is None:
        weights = np.ones(np.shape(ydata))

    parvals = params.valuesdict()

    nt = parvals['nt']

    # Scintillation timescale model
    xdata_t = xdata[:nt]
    ydata_t = ydata[:nt]
    weights_t = weights[:nt]
    residuals_t = tau_acf_model(params, xdata_t, ydata_t, weights_t)

    # Scintillation bandwidth model
    xdata_f = xdata[nt:]
    ydata_f = ydata[nt:]
    weights_f = weights[nt:]
    residuals_f = dnu_acf_model(params, xdata_f, ydata_f, weights_f)

    return np.concatenate((residuals_t, residuals_f))


def scint_acf_model_2d_approx(params, tdata, fdata, ydata, weights):
    """
    Fit an approximate 2D ACF function
    """

    if weights is None:
        weights = np.ones(np.shape(ydata))

    parvals = params.valuesdict()

    amp = parvals['amp']
    dnu = parvals['dnu']
    tau = parvals['tau']
    alpha = parvals['alpha']
    phasegrad = parvals['phasegrad']
    freq = parvals['freq']
    tobs = parvals['tobs']
    wn = parvals['wn']
    nt = len(tdata)
    nf = len(fdata)

    tdata = np.reshape(tdata, (nt, 1))
    fdata = np.reshape(fdata, (1, nf))

    model = amp * np.exp(-(abs((tdata / tau) + 2 * phasegrad *
                               ((dnu / np.log(2)) / freq)**(1 / 6) *
                               (fdata / (dnu / np.log(2))))**(3 * alpha / 2) +
                         abs(fdata / (dnu / np.log(2)))**(3 / 2))**(2 / 3))
    # multiply by triangle function
    model = np.multiply(model, 1-np.divide(abs(tdata), tobs))
    model = np.fft.fftshift(model)
    model[1, 1] = model[1, 1] + wn  # add white noise spike
    model = np.fft.fftshift(model)
    model = np.transpose(model)

    return (ydata - model) * weights


def scint_acf_model_2d(params, ydata, weights):
    """
    Fit an analytical 2D ACF function
    """
    from scint_sim import ACF

    if weights is None:
        weights = np.ones(np.shape(ydata))

    parvals = params.valuesdict()

    tau = parvals['tau']
    dnu = parvals['dnu']
    alpha = parvals['alpha']
    ar = parvals['ar']
    phasegrad_x = parvals['phasegrad_x']
    phasegrad_y = parvals['phasegrad_y']
    wn = parvals['wn']
    amp = parvals['amp']

    V_x = parvals['v_x']
    V_y = parvals['v_y']
    # psi = parvals['psi']

    tobs = parvals['tobs']
    bw = parvals['bw']
    nt = 2 * parvals['nt']
    nf = 2 * parvals['nf']
    dt = 2 * tobs / nt
    df = 2 * bw / nf

    nt_crop = len(ydata[0])
    nf_crop = len(ydata)

    taumax = (nt_crop / nt) * tobs / tau
    dnumax = (nf_crop / nf) * bw / dnu

    acf = ACF(s_max=taumax, dnu_max=dnumax, ns=nt_crop, nf=nf_crop, ar=ar, alpha=alpha,
              phasegrad_x=phasegrad_x, phasegrad_y=phasegrad_y, amp=amp, V_x=V_x, V_y=V_y,
              psi=None, use_t=False)
    acf.calc_acf()
    model = acf.acf

    model[int(nf_crop / 2) + 1, int(nt_crop / 2) + 1] += wn  # add white noise spike

    triangle_t = 1 - np.divide(np.tile(np.abs(np.linspace(-nt_crop * dt / 2, nt_crop * dt / 2,
                                                          nt_crop)), (nf_crop, 1)),
                                                          tobs)
    triangle_f = np.transpose(1 - np.divide(np.tile(np.abs(np.linspace(-nf_crop * df / 2, nf_crop * df / 2, nf_crop)),
                                       (nt_crop, 1)), bw))
    triangle = np.multiply(triangle_t, triangle_f)
    model = np.multiply(model, triangle)  # multiply by triangle function

    return (ydata - model) * weights


def tau_sspec_model(params, xdata, ydata, weights):
    """
    Fit 1D function to cut through ACF for scintillation timescale.
    Exponent is 5/3 for Kolmogorov turbulence.
        amp = Amplitude
        tau = timescale at 1/e
        alpha = index of exponential function. 2 is Gaussian, 5/3 is Kolmogorov
        wn = white noise spike in ACF cut
    """

    if weights is None:
        weights = np.ones(np.shape(ydata))

    amp = params['amp']
    tau = params['tau']
    alpha = params['alpha']
    wn = params['wn']

    model = amp*np.exp(-np.divide(xdata, tau)**(alpha))
    model[0] = model[0] + wn  # add white noise spike
    # Multiply by triangle function
    model = np.multiply(model, 1-np.divide(xdata, max(xdata)))

    model_flipped = model[::-1]
    model = np.concatenate((model, model_flipped))
    model = model[0:2*len(xdata)-1]
    # Get Fourier model
    model = np.fft.fft(model)
    model = np.real(model)
    model = model[0:len(xdata)]

    return (ydata - model) * weights


def dnu_sspec_model(params, xdata, ydata, weights):
    """
    Fit 1D function to cut through ACF for decorrelation bandwidth.
    Default function has is exponential with dnu measured at half power
        amp = Amplitude
        dnu = bandwidth at 1/2 power
        wn = white noise spike in ACF cut
    """
    if weights is None:
        weights = np.ones(np.shape(ydata))

    amp = params['amp']
    dnu = params['dnu']
    wn = params['wn']

    model = amp*np.exp(-np.divide(xdata, dnu/np.log(2)))
    model[0] = model[0] + wn  # add white noise spike
    # Multiply by triangle function
    model = np.multiply(model, 1-np.divide(xdata, max(xdata)))

    model_flipped = model[::-1]
    model = np.concatenate((model, model_flipped))
    model = model[0:2*len(xdata)-1]
    # Get Fourier model
    model = np.fft.fft(model)
    model = np.real(model)
    model = model[0:len(xdata)]

    return (ydata - model) * weights


def scint_sspec_model(params, xdata, ydata, weights):
    """
    Fit both tau (tau_acf_model) and dnu (dnu_acf_model) simultaneously
    """

    # if weights is None:
    #     weights = np.ones(np.shape(ydata))
    #
    # parvals = params.valuesdict()
    #
    # nt = parvals['nt']
    #
    # # Scintillation timescale model
    # xdata_t = xdata[:nt]
    # ydata_t = ydata[:nt]
    # weights_t = weights[:nt]
    # residuals_t = tau_sspec_model(params, xdata_t, ydata_t, weights_t)
    #
    # # Scintillation bandwidth model
    # xdata_f = xdata[nt:]
    # ydata_f = ydata[nt:]
    # weights_f = weights[nt:]
    # residuals_f = dnu_sspec_model(params, xdata_f, ydata_f, weights_f)
    #
    # return np.concatenate((residuals_t, residuals_f))


def arc_power_curve(params, xdata, ydata, weights):
    """
    Returns a template for the power curve in secondary spectrum vs
    sqrt(curvature) or normalised fdop
    """

    if weights is None:
        weights = np.ones(np.shape(ydata))

    model = []
    return (ydata - model) * weights


def thin_screen(params, xdata, ydata, weights):
    """
    Thin screen effective velocity
    """

    if weights is None:
        weights = np.ones(np.shape(ydata))

    model = []
    return (ydata - model) * weights


def fit_parabola(x, y):
    """
    Fit a parabola and return the value and error for the peak
    """

    # increase range to help fitter
    ptp = np.ptp(x)
    x = x*(1000/ptp)

    # Do the fit
    params, pcov = np.polyfit(x, y, 2, cov=True)
    yfit = params[0]*np.power(x, 2) + params[1]*x + params[2]  # y values

    # Get parameter errors
    errors = []
    for i in range(len(params)):  # for each parameter
        errors.append(np.absolute(pcov[i][i])**0.5)

    # Get parabola peak and error
    peak = -params[1]/(2*params[0])  # Parabola max (or min)
    peak_error = np.sqrt((errors[1]**2)*((1/(2*params[0]))**2) +
                         (errors[0]**2)*((params[1]/2)**2))  # Error on peak

    peak = peak*(ptp/1000)
    peak_error = peak_error*(ptp/1000)

    return yfit, peak, peak_error


def fit_log_parabola(x, y):
    """
    Fit a log-parabola and return the value and error for the peak
    """

    # Take the log of x
    logx = np.log(x)
    ptp = np.ptp(logx)
    x = logx*(1000/ptp)  # increase range to help fitter

    # Do the fit
    yfit, peak, peak_error = fit_parabola(x, y)
    frac_error = peak_error/peak

    peak = np.e**(peak*ptp/1000)
    # Average the error asymmetries
    peak_error = frac_error*peak

    return yfit, peak, peak_error


def arc_curvature(params, ydata, weights, true_anomaly,
                  vearth_ra, vearth_dec, vfit=False, modelonly=False):
    """
    arc curvature model

        ydata: arc curvature (vfit=False), or 
               1 / sqrt(arc curvature) (when vfit=True)
    """

    # ensure dimensionality of arrays makes sense
    if hasattr(ydata,  "__len__"):
        ydata = ydata.squeeze()
        weights = weights.squeeze()
        true_anomaly = true_anomaly.squeeze()
        vearth_ra = vearth_ra.squeeze()
        vearth_dec = vearth_dec.squeeze()

    kmpkpc = 3.085677581e16

    # Other parameters in lower-case
    d = params['d']  # pulsar distance in kpc
    try:
        s = params['s']  # fractional screen distance
    except:
        d_s = params['d_s'] # screen distance in kpc
        s = 1 - d_s / d
    d = d * kmpkpc  # kms

    veff_ra, veff_dec, vp_ra, vp_dec = \
        effective_velocity_annual(params, true_anomaly,
                                  vearth_ra, vearth_dec)

    if 'vism_ra' in params.keys():
        vism_ra = params['vism_ra']
        vism_dec = params['vism_dec']
    else:
        vism_ra = 0
        vism_dec = 0

    if 'vism_psi' in params.keys():  # anisotropic case
        psi = params['psi']*np.pi/180  # anisotropy angle
        vism_psi = params['vism_psi']  # vism in direction of anisotropy
        veff2 = (veff_ra*np.sin(psi) + veff_dec*np.cos(psi) - vism_psi)**2
    else:  # isotropic
        veff2 = (veff_ra - vism_ra)**2 + (veff_dec - vism_dec)**2

    # Calculate curvature model
    model = d * s * (1 - s)/(2 * veff2)  # in 1/(km * Hz**2)
    # Convert to 1/(m * mHz**2) for beta in 1/m and fdop in mHz
    model = model/1e9

    if weights is None:
        weights = np.ones(np.shape(ydata))

    if vfit:
        model = 1e3 / np.sqrt(model)

    if modelonly:
        return model

    return (ydata - model) * weights


"""
Below: Models that do not return residuals for a fitter
"""


def effective_velocity_annual(params, true_anomaly, vearth_ra, vearth_dec):
    """
    Effective velocity with annual and pulsar terms
        Note: Does NOT include IISM velocity, but returns veff in IISM frame
    """
    # Define some constants
    v_c = 299792.458  # km/s
    kmpkpc = 3.085677581e16
    secperyr = 86400*365.2425
    masrad = np.pi/(3600*180*1000)

    # tempo2 parameters from par file in capitals
    if 'PB' in params.keys():
        A1 = params['A1']  # projected semi-major axis in lt-s
        PB = params['PB']  # orbital period in days
        ECC = params['ECC']  # orbital eccentricity
        OM = params['OM']*np.pi/180  # longitude of periastron rad
        # Note: fifth Keplerian param T0 used in true anomaly calculation
        KIN = params['KIN']*np.pi/180  # inclination
        KOM = params['KOM']*np.pi/180  # longitude ascending node

        # Calculate pulsar velocity aligned with the line of nodes (Vx) and
        #   perpendicular in the plane (Vy)
        vp_0 = (2 * np.pi * A1 * v_c) / (np.sin(KIN) * PB * 86400 *
                                         np.sqrt(1 - ECC**2))
        vp_x = -vp_0 * (ECC * np.sin(OM) + np.sin(true_anomaly + OM))
        vp_y = vp_0 * np.cos(KIN) * (ECC * np.cos(OM) + np.cos(true_anomaly
                                                               + OM))
    else:
        vp_x = 0
        vp_y = 0

    if 'PMRA' in params.keys():
        PMRA = params['PMRA']  # proper motion in RA
        PMDEC = params['PMDEC']  # proper motion in DEC
    else:
        PMRA = 0
        PMDEC = 0

    # other parameters in lower-case
    d = params['d']  # pulsar distance in kpc
    try:
        s = params['s']  # fractional screen distance
    except:
        d_s = params['d_s'] # screen distance in kpc
        s = 1 - d_s / d
    d = d * kmpkpc  # distance in km

    pmra_v = PMRA * masrad * d / secperyr
    pmdec_v = PMDEC * masrad * d / secperyr

    # Rotate pulsar velocity into RA/DEC
    vp_ra = np.sin(KOM) * vp_x + np.cos(KOM) * vp_y
    vp_dec = np.cos(KOM) * vp_x - np.sin(KOM) * vp_y

    # find total effective velocity in RA and DEC
    veff_ra = s * vearth_ra + (1 - s) * (vp_ra + pmra_v)
    veff_dec = s * vearth_dec + (1 - s) * (vp_dec + pmdec_v)

    return veff_ra, veff_dec, vp_ra, vp_dec
