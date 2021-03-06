from __future__ import division

import inspect
import numpy as np
from scipy.optimize import root
# from ancil import natural, cmip6_volcanic, cmip6_solar, historical_scaling
# from constants import molwt, lifetime, radeff
# from constants.general import M_ATMOS
# from forcing import ozone_tr, ozone_st, h2o_st, contrails, aerosols, bc_snow,\
                                         # landuse

emissions=False,
other_rf=0.0,
q=np.array([0.33,0.41]),
tcrecs=np.array([2.0,3.63]),
C = 8.5,
Co = 78,
gamma = 0.62,
lambda_ = 1.21,
epsilon = 1.42,
d=np.array([239.0,4.1]),
a=np.array([0.2173,0.2240,0.2824,0.2763]),
tau=np.array([1000000,394.4,36.54,4.304]),
r0=35.0,
rc=0.019,
rt=4.165,
F2x=3.71,
iirf_max=97.0,
tcr_dbl=69.661,
C_pi=np.array([278., 722., 273., 34.497] + [0.]*25 + [13.0975, 547.996]),
restart_in=False,
restart_out=False,
F_volcanic=cmip6_volcanic.Forcing.volcanic,
F_solar=cmip6_solar.Forcing.solar,
F_contrails=0.,
F_landuse=0.,
aviNOx_frac=0.,
fossilCH4_frac=0.,
natural=natural.Emissions.emissions,
efficacy=np.array([1.]*9 + [3.] + [1.]*3),
scale=None,
oxCH4_frac=0.61,
ghg_forcing="Etminan",
stwv_from_ch4=None,
b_aero = np.array([-6.2227e-3, 0.0, -3.8392e-4, -1.16551e-3, 1.601537e-2,
  -1.45339e-3, -1.55605e-3]),
b_tro3 = np.array([2.8249e-4, 1.0695e-4, -9.3604e-4, 99.7831e-4]),
ghan_params = np.array([-1.95011431, 0.01107147, 0.01387492]),
stevens_params = np.array([0.001875, 0.634, 60.]),
useMultigas=True,
useStevenson=True,
lifetimes=False,
aerosol_forcing="aerocom+ghan",
scaleAerosolAR5=True,
fixPre1850RCP=True,
useTropO3TFeedback=True,
scaleHistoricalAR5=False,
contrail_forcing='NOx',
kerosene_supply=0.,
landuse_forcing='co2'

# Conversion between ppm CO2 and GtC emissions
ppm_gtc     = M_ATMOS/1e18*molwt.C/molwt.AIR

# Conversion between ppb/ppt concentrations and Mt/kt emissions
# in the RCP databases ppb = Mt and ppt = kt so factor always 1e18
emis2conc = M_ATMOS/1e18*np.asarray(molwt.aslist)/molwt.AIR

# Funny units for nitrogen emissions - N2O is expressed in N2 equivalent
n2o_sf = molwt.N2O/molwt.N2
emis2conc[2] = emis2conc[2] / n2o_sf

# Convert any list to a numpy array for (a) speed and (b) consistency.
# Goes through all variables in scope and converts them.
frame = inspect.currentframe()
args, _, _, values = inspect.getargvalues(frame)
for arg_to_check in args:
    if type(values[arg_to_check]) is list:
        exec(arg_to_check + '= np.array(' + arg_to_check + ')')

# Set up the output timeseries variables depending on options and perform
# basic sense checks
if useMultigas:
    ngas = 31
    nF   = 13
    if type(emissions) is not np.ndarray or emissions.shape[1] != 40:
        raise ValueError(
          "emissions timeseries should be a nt x 40 numpy array")
    carbon_boxes_shape = (emissions.shape[0], a.shape[0])
    thermal_boxes_shape = (emissions.shape[0], d.shape[0])
    nt = emissions.shape[0]
    if np.isscalar(fossilCH4_frac):
        fossilCH4_frac = np.ones(nt) * fossilCH4_frac
    # If custom gas lifetimes are supplied, use them, else import defaults
    if type(lifetimes) is np.ndarray:
        if len(lifetimes)!=ngas:
            raise ValueError(
              "custom GHG lifetime array must have " + str(ngas) +
              " elements")
    else:
        lifetimes = lifetime.aslist
    # Select the desired GHG forcing relationship and populate
    # stratospheric water vapour from methane scale factor if not specified
    # by user
    if ghg_forcing.lower()=="etminan":
        from .forcing.ghg import etminan as ghg
        if stwv_from_ch4==None: stwv_from_ch4=0.12
    elif ghg_forcing.lower()=="myhre":
        from .forcing.ghg import myhre as ghg
        if stwv_from_ch4==None: stwv_from_ch4=0.15
    else:
        raise ValueError(
          "ghg_forcing should be 'etminan' (default) or 'myhre'")

    # Check natural emissions and convert to 2D array if necessary
    if type(natural) in [float,int]:
        natural = natural * np.ones((nt,2))
    elif type(natural) is np.ndarray:
        if natural.ndim==1:
            if natural.shape[0]!=2:
                raise ValueError(
                  "natural emissions should be a 2-element or nt x 2 " +
                  "array")
            natural = np.tile(natural, nt).reshape((nt,2))
        elif natural.ndim==2:
            if natural.shape[1]!=2 or natural.shape[0]!=nt:
                raise ValueError(
                  "natural emissions should be a 2-element or nt x 2 " +
                  "array")
    else:
        raise ValueError(
          "natural emissions should be a scalar, 2-element, or nt x 2 " +
          "array")

    # check scale factor is correct shape. If 1D inflate to 2D
    if scale is None:
        scale = np.ones((nt,nF))
    elif scale.shape[-1]==nF:
        if scale.ndim==2 and scale.shape[0]==nt:
            pass
        elif scale.ndim==1:
            scale = np.tile(scale, nt).reshape((nt,nF))
    else:
        raise ValueError("in multi-gas mode, scale should be None, or a "+
          "(13,) or (nt, 13) array")

    # if scaling the historical time series to match AR5, apply these
    # factors to whatever the user specifies
    if scaleHistoricalAR5:
        scale=scale*historical_scaling.all[:nt,:]

else:
    ngas = 1
    nF   = 1
    if type(emissions) is np.ndarray:
        if emissions.ndim != 1:
            raise ValueError(
              "In CO2-only mode, emissions should be a 1D array")
        nt = emissions.shape[0]
        carbon_boxes_shape = (nt, a.shape[0])
        thermal_boxes_shape = (nt, d.shape[0])
    elif type(other_rf) is np.ndarray:
        if other_rf.ndim != 1:
            raise ValueError(
              "In CO2-only mode, other_rf should be a 1D array")
        nt = other_rf.shape[0]
        carbon_boxes_shape = (nt, a.shape[0])
        thermal_boxes_shape = (nt, d.shape[0])
        emissions = np.zeros(nt)
    else:
        raise ValueError(
          "Neither emissions or other_rf is defined as a timeseries")

    # check scale factor is correct shape - either scalar or 1D
    if scale is None:
        scale = np.ones(nt)
    elif scale.ndim==1 and scale.shape[0]==nt:
        pass
    else:
        raise ValueError("in CO2-only mode, scale should be None, a "+
          "scalar or a (nt,) array")

    # if scaling the historical time series to match AR5, apply these
    # factors to whatever the user specifies
    if scaleHistoricalAR5:
        scale=scale*historical_scaling.co2[:nt]

# If TCR and ECS are supplied, calculate the q1 and q2 model coefficients
# (overwriting any other q array that might have been supplied)
# ref eq. (4) and (5) of Millar et al ACP (2017)
k = 1.0 - (d/tcr_dbl)*(1.0 - np.exp(-tcr_dbl/d))    # Allow TCR to vary
if type(tcrecs) is np.ndarray:
    # if ECS and TCR are not time-varying, expand them to 2D array anyway
    if tcrecs.ndim==1:
        if len(tcrecs)!=2:
            raise ValueError(
              "Constant TCR and ECS should be a 2-element array")
        tcrecs = np.ones((nt, 2)) * tcrecs
    elif tcrecs.ndim==2:
        if tcrecs.shape!=(nt, 2):
            raise ValueError(
              "Transient TCR and ECS should be a nt x 2 array")
    q  = (1.0 / F2x) * (1.0/(k[0]-k[1])) * np.array([
        tcrecs[:,0]-tcrecs[:,1]*k[1],tcrecs[:,1]*k[0]-tcrecs[:,0]]).T

# Check a and tau are same size
if a.ndim != 1:
    raise ValueError("a should be a 1D array")
if tau.ndim != 1:
    raise ValueError("tau should be a 1D array")
if len(a) != len(tau):
    raise ValueError("a and tau should be the same size")
if not np.isclose(np.sum(a), 1.0):
    raise ValueError("a should sum to one")

F = np.zeros((nt, nF))
C_acc = np.zeros(nt)
iirf = np.zeros(nt)
R_i = np.zeros(carbon_boxes_shape)
T_j = np.zeros(thermal_boxes_shape)

C = np.zeros((nt, ngas))
T = np.zeros(nt)
C_0 = np.copy(C_pi)

if restart_in:
    R_i[0]=restart_in[0]
    T_j[0]=restart_in[1]
    C_acc[0] = restart_in[2]
else:
    # Initialise the carbon pools to be correct for first timestep in
    # numerical method
    if useMultigas:
        R_i[0,:] = a * (np.sum(emissions[0,1:3])) / ppm_gtc
    else:
        R_i[0,:] = a * emissions[0,np.newaxis] / ppm_gtc

# CO2 is a delta from pre-industrial. Other gases are absolute MMR
C[0,0] = np.sum(R_i[0,:],axis=-1)

if useMultigas:
    C[0,1:] = C_0[1:]

    # CO2, CH4 and methane are co-dependent
    F[0,0:3] = ghg(C[0,0:3]+np.array([C_pi[0],0,0]), C_pi[0:3], F2x=F2x)

    # Minor (F- and H-gases) are linear in concentration
    # the factor of 0.001 here is because radiative efficiencies are given
    # in W/m2/ppb and concentrations of minor gases are in ppt.
    F[0,3] = np.sum((C[0,3:] - C_pi[3:]) * radeff.aslist[3:] * 0.001)

    # Tropospheric ozone:
    if useStevenson:
        F[0,4] = ozone_tr.stevenson(emissions[0,:], C[0,1],
            T=T_j[0,0],
            feedback=useTropO3TFeedback,
            fix_pre1850_RCP=fixPre1850RCP)
    else:
        F[0,4] = ozone_tr.regress(emissions[0,:], beta=b_tro3)

    # Stratospheric ozone depends on concentrations of ODSs (index 15-30)
    F[0,5] = ozone_st.magicc(C[0,15:], C_pi[15:])

    # Stratospheric water vapour is a function of the methane ERF
    F[0,6] = h2o_st.linear(F[0,1], ratio=stwv_from_ch4)

    # Forcing from contrails. No climate feedback so can live outside
    # of forward model in this version
    if contrail_forcing.lower()[0]=='n':   # from NOx emissions
        F[:,7] = contrails.from_aviNOx(emissions, aviNOx_frac)
    elif contrail_forcing.lower()[0]=='f': # from kerosene production
        F[:,7] = contrails.from_fuel(kerosene_supply)
    elif contrail_forcing.lower()[0]=='e': # external forcing timeseries
        F[:,7] = F_contrails
    else:
        raise ValueError("contrails must be one of 'NOx' (estimated "+
          "from NOx emissions), 'fuel' (estimated from annual jet fuel "+
          "supplied) or 'external' (an external forcing time series).")

    # Forcing from aerosols - again no feedback dependence
    if aerosol_forcing.lower()=='stevens':
        F[:,8] = aerosols.Stevens(emissions, stevens_params=stevens_params)
    elif 'aerocom' in aerosol_forcing.lower():
        F[:,8] = aerosols.aerocom_direct(emissions, beta=b_aero)
        if 'ghan' in aerosol_forcing.lower():
            F[:,8] = F[:,8] + aerosols.ghan_indirect(emissions,
              scale_AR5=scaleAerosolAR5,
              fix_pre1850_RCP=fixPre1850RCP,
              ghan_params=ghan_params)
    else:
        raise ValueError("aerosol_forcing should be one of 'stevens', " +
          "aerocom, aerocom+ghan")

    # Black carbon on snow - no feedback dependence
    F[:,9] = bc_snow.linear(emissions)

    # Land use change - either use a scaling with cumulative CO2 emissions
    # or an external time series
    if landuse_forcing.lower()[0]=='c':
        F[:,10] = landuse.cumulative(emissions)
    elif landuse_forcing.lower()[0]=='e':
        F[:,10] = F_landuse
    else:
        raise ValueError(
          "landuse_forcing should be one of 'co2' or 'external'")

    # Volcanic and solar copied straight to the output arrays
    F[:,11] = F_volcanic
    F[:,12] = F_solar

    # multiply by scale factors
    F[0,:] = F[0,:] * scale[0,:]

else: # this needs to be included in the forcing.ghg module really
    if np.isscalar(other_rf):
        F[0,0] = (F2x/np.log(2.)) * np.log(
          (C[0,0] + C_pi[0]) / C_pi[0]) + other_rf
    else:
        F[0,0] = (F2x/np.log(2.)) * np.log(
          (C[0,0] + C_pi[0]) / C_pi[0]) + other_rf[0]

    F[0,0] = F[0,0] * scale[0]

if restart_in == False:
    # Update the thermal response boxes
    T_j[0,0] = T[0] + ( np.sum(F[0,:]) - lambda_*T[0] - epsilon * gamma * (T[0] - 0)) / C
    T_j[0,1] = 0 + gamma * (T[0] - 0) / Co

# the GMST is the top temperature of the twolayer_model
T[0]=T_j[0,0]

for t in range(1,nt):
    # Calculate the parametrised iIRF and check if it is over the maximum
    # allowed value
    iirf[t] = rc * C_acc[t-1]  + rt*T[t-1]  + r0
    if iirf[t] >= iirf_max:
        iirf[t] = iirf_max

    # Linearly interpolate a solution for alpha
    if t == 1:
        time_scale_sf = (
          root(iirf_interp_funct,0.16,args=(a,tau,iirf[t])))['x']
    else:
        time_scale_sf = (root(iirf_interp_funct,time_scale_sf,args=(
          a,tau,iirf[t])))['x']

    # Multiply default timescales by scale factor
    tau_new = tau * time_scale_sf

    if useMultigas:
        # 1. Concentrations
        # a. CARBON DIOXIDE
        # Firstly add any oxidised methane from last year to the CO2 pool
        oxidised_CH4 = ((C[t-1,1]-C_pi[1]) *
          (1.0 - np.exp(-1.0/lifetimes[1])) *
          (molwt.C/molwt.CH4 * 0.001 * oxCH4_frac * fossilCH4_frac[t]))
        oxidised_CH4 = np.max((oxidised_CH4, 0))

        # Compute the updated concentrations box anomalies from the decay
        # of the previous year and the additional emissions
        R_i[t,:] = R_i[t-1,:]*np.exp(-1.0/tau_new) + a*(np.sum(
            emissions[t,1:3]) + oxidised_CH4) / ppm_gtc
        # Sum the boxes to get the total concentration anomaly
        C[t,0] = np.sum(R_i[...,t,:],axis=-1)
        # Calculate the additional carbon uptake
        C_acc[t] =  C_acc[t-1] + 0.5*(np.sum(emissions[t-1:t+1,1:3])) - (
            C[t,0] - C[t-1,0])*ppm_gtc

        # b. METHANE
        C[t,1] = C[t-1,1] - C[t-1,1]*(1.0 - np.exp(-1.0/lifetimes[1])) + (
          natural[t,0] + 0.5*(emissions[t,3] + emissions[t-1,3])
          ) / emis2conc[1]

        # c. NITROUS OXIDE
        C[t,2] = C[t-1,2] - C[t-1,2]*(1.0 - np.exp(-1.0/lifetimes[2])) + (
          natural[t,1] + 0.5*(emissions[t,4] + emissions[t-1,4])
          ) / emis2conc[2]

        # d. OTHER WMGHGs
        C[t,3:] = C[t-1,3:] - C[t-1,3:]*(1.0 - np.exp(-1.0/np.array(
          lifetimes[3:]))) + (0.5 * (
          emissions[t,12:] + emissions[t-1,12:])) / emis2conc[3:]

        # 2. Radiative forcing
        F[t,0:3] = ghg(C[t,0:3]+np.array([C_pi[0],0,0]), C_pi[0:3], F2x=F2x)
        F[t,3] = np.sum((C[t,3:] - C_pi[3:]) * radeff.aslist[3:] * 0.001)
        if useStevenson:
            F[t,4] = ozone_tr.stevenson(emissions[t,:], C[t,1], T=T[t-1],
              feedback=useTropO3TFeedback,
              fix_pre1850_RCP=fixPre1850RCP)
        else:
            F[t,4] = ozone_tr.regress(emissions[t,:], beta=b_tro3)
        F[t,5] = ozone_st.magicc(C[t,15:], C_pi[15:])
        F[t,6] = h2o_st.linear(F[t,1], ratio=stwv_from_ch4)

        # multiply by scale factors
        F[t,:] = F[t,:] * scale[t,:]

        # 3. Temperature
        # Update the thermal response boxes
        T_j[t,0] = T_j[t-1,0] + ( np.sum(F[t-1,:]) - lambda_*T_j[t-1,0] - epsilon * gamma * (T_j[t-1,0] - T_j[t-1,1])) / C
        T_j[t,1] = T_j[t-1,1] + gamma * (T_j[t-1,0] - T_j[t-1,1]) / Co
        # total temperature is the surface temperature of the 2-layer model
        T[t]=T_j[t,0]

    else:
        R_i[t,:] = R_i[t-1,:]*np.exp(-1.0/tau_new) + a*(np.sum(
            emissions[t])) / ppm_gtc
        # Sum the boxes to get the total concentration anomaly
        C[t,0] = np.sum(R_i[...,t,:],axis=-1)
        # Calculate the additional carbon uptake
        C_acc[t] =  C_acc[t-1] + 0.5*(np.sum(emissions[t-1:t+1])) - (
            C[t,0] - C[t-1,0])*ppm_gtc

        if np.isscalar(other_rf):
            F[t,0] = (F2x/np.log(2.)) * np.log(
                (C[t,0] + C_pi[0]) / C_pi[0]) + other_rf
        else:
            F[t,0] = (F2x/np.log(2.)) * np.log(
                (C[t,0] + C_pi[0]) / C_pi[0]) + other_rf[t]

        F[t,0] = F[t,0] * scale[t]

        T_j[t,0] = T_j[t-1,0] + ( np.sum(F[t-1,:]) - lambda_*T_j[t-1,0] - epsilon * gamma * (T_j[t-1,0] - T_j[t-1,1])) / C
        T_j[t,1] = T_j[t-1,1] + gamma * (T_j[t-1,0] - T_j[t-1,1]) / Co
        # total temperature is the surface temperature of the 2-layer model
        T[t]=T_j[t,0]

# add delta CO2 concentrations to initial value
C[:,0] = C[:,0] + C_0[0]
