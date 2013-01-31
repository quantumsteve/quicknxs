#-*- coding: utf-8 -*-
'''
Module for data readout and evaluation of the SNS Magnetism Reflectometer.
Can also be used stand alone for e.g. interactive processing
or scripts, therefore it is kept as only one file. The only dependencies
are numpy and the h5py module, which is an interface to the HDF5 file format
C-library, on which Nexus files are based.

The NXSData object reads a full .nxs file (histogram and event mode) and analysis
it's content for the channels that have been measured. It can be use as a list
or dictionary to access these channels as MRDataset objects.

The Relflectivity extracts a reflectiviy from a MRDataset object and
storing the result as well as some intermediate data in itself as attributes.
'''

import os
from numpy import *
import h5py
from time import time
# ignore zero devision error
#seterr(invalid='ignore')

'''
Parameters needed for some calculations.
'''
H_OVER_M_NEUTRON=3.956034e-7 # h/m_n [m²/s]

TOF_DISTANCE=21.2535 # m
#RAD_PER_PIX=0.0002734242
#RAD_PER_PIX=0.00027429694 # arctan(212.8mm/2/2550.5mm)/152pix
RAD_PER_PIX=0.00027445599 # arctan(212.8mm/2/2550.5mm)/152pix
DETECTOR_X_REGION=(8, 295)

# position and maximum deviation of polarizer and analzer in it's working position
ANALYZER_IN=(0., 100.)
POLARIZER_IN=(-348., 50.)

MAPPING_FULLPOL=(
                 (u'++', u'entry-Off_Off'),
                 (u'--', u'entry-On_On'),
                 (u'+-', u'entry-Off_On'),
                 (u'-+', u'entry-On_Off'),
                 )
MAPPING_HALFPOL=(
                 (u'+', u'entry-Off_Off'),
                 (u'-', u'entry-On_Off'),
                 )
MAPPING_UNPOL=(
               (u'x', u'entry-Off_Off'),
               )
MAPPING_EFIELD=(
                (u'0V', u'entry-Off_Off'),
                (u'+V', u'entry-On_Off'),
                (u'-V', u'entry-Off_On'),
                )

class NXSData(object):
  '''
  Class for readout and evaluation of histogram and event mode .nxs files,
  which also stores the data to be accessed by attributes.
  
  The object can be used as a ordered dictionary or list of channels,
  where each channel is a MRDataset object.
  
  The generator takes several keyword arguments to control the readout:
  
    * use_caching=False: If files should be cached for faster future readouts (last 20 files)
    * bin_type='linear: 'linear'/'1/x' - use linear or 1/x spacing for ToF channels in event mode
    * bins=40: Number of ToF bins for event mode
  '''
  DEFAULT_OPTIONS=dict(bin_type='linear', bins=40, use_caching=False, callback=None)
  COUNT_THREASHOLD=100
  MAX_CACHE=20
  _cache=[]

  def __new__(cls, filename, **options):
    all_options=dict(cls.DEFAULT_OPTIONS)
    for key, value in options.items():
      if not key in all_options:
        raise ValueError, "%s is not a known option parameter"%key
      all_options[key]=value
    filename=os.path.abspath(filename)
    cached_names=[item.origin for item in cls._cache]
    if all_options['use_caching'] and filename in cached_names:
      cache_index=cached_names.index(filename)
      cached_object=cls._cache[cache_index]
      if cached_object._options==all_options:
        return cached_object
    # else
    self=object.__new__(cls)
    self._options=all_options
    # create empty attributes
    self._channel_names=[]
    self._channel_origin=[]
    self._channel_data=[]
    self.measurement_type=""
    self.origin=filename
    # process the file
    self._read_times=[]
    self._read_file(filename)
    if all_options['use_caching']:
      if filename in cached_names:
        cache_index=cached_names.index(filename)
        cls._cache.pop(cache_index)
      if len(cls._cache)>=cls.MAX_CACHE:
        cls._cache.pop(0)
      cls._cache.append(self)
      cls._cached_names.append(filename)
    return self

  def _read_file(self, filename):
    '''
    Load data from a Nexus file.
    '''
    start=time()
    if self._options['callback']:
      self._options['callback'](0.)
    nxs=h5py.File(filename, mode='r')
    # analyze channels
    channels=nxs.keys()
    for channel in list(channels):
      if nxs[channel][u'total_counts'].value[0]<self.COUNT_THREASHOLD:
        channels.remove(channel)
    if len(channels)==0:
      return None
    ana=nxs[channels[0]]['instrument/analyzer/AnalyzerLift/value'].value[0]
    pol=nxs[channels[0]]['instrument/polarizer/PolLift/value'].value[0]

    # select the type of measurement that has been used
    if abs(ana-ANALYZER_IN[0])<ANALYZER_IN[1]:
      self.measurement_type='Polarization Analysis'
      mapping=MAPPING_FULLPOL
    elif abs(pol-POLARIZER_IN[0])<POLARIZER_IN[1]:
      self.measurement_type='Polarized'
      mapping=MAPPING_HALFPOL
    elif len(channels)==3:
      self.measurement_type='Electric Field'
      mapping=MAPPING_EFIELD
    else:
      self.measurement_type='Unpolarized'
      mapping=MAPPING_UNPOL

    if self._options['callback']:
      progress=1./(len(channels)+1)
      self._options['callback'](progress)
    self._read_times.append(time()-start)
    i=2
    for dest, channel in mapping:
      if channel not in channels:
        continue
      raw_data=nxs[channel]
      if filename.endswith('event.nxs'):
        data=MRDataset.from_event(raw_data, self._options)
      else:
        data=MRDataset.from_histogram(raw_data, self._options)
      self._channel_data.append(data)
      self._channel_names.append(dest)
      self._channel_origin.append(channel)
      if self._options['callback']:
        progress=float(i)/(len(channels)+1)
        self._options['callback'](progress)
      i+=1
      self._read_times.append(time()-self._read_times[-1]-start)
    #print time()-start
    nxs.close()

  def __getitem__(self, item):
    if type(item)==int:
      return self._channel_data[item]
    else:
      if item in self._channel_names:
        return self._channel_data[self._channel_names.index(item)]
      elif item in self._channel_origin:
        return self._channel_data[self._channel_origin.index(item)]
      else:
        raise KeyError, "No such channel: %s"%str(item)

  def __len__(self):
    return len(self._channel_data)

  def __repr__(self):
    output=self.__class__.__name__+'({'
    spacer0=" "*(len(output)-1)
    for key, value in self.items():
      output+="\n%s '%s': %s,"%(spacer0, key, repr(value))
    output=output[:-1]+'\n'+spacer0+'})'
    return output

  def keys(self):
    return self._channel_names

  def values(self):
    return self._channel_data

  def items(self):
    return zip(self.keys(), self.values())

  def numitems(self):
    ''':return: three items tuples of the channel index, name and data'''
    return zip(xrange(len(self.keys())), self.keys(), self.values())

  def __iter__(self):
    for item in self.values():
      yield item

class MRDataset(object):
  '''
  Representation of one measurement channel of the reflectometer
  including meta data.
  '''
  proton_charge=0.
  total_counts=0
  tof_edges=None
  dangle=0.
  dangle0=0.
  sangle=0.
  ai=None
  dpix=0
  beam_width=0.
  lambda_center=3.37
  xydata=None
  xtofdata=None
  data=None
  _Q=None
  _I=None
  _dI=None

  def __init__(self):
    '''
    Initialize an empty dataset. To actually load a Nexus file channel
    use the class methods from_histogram or from_event.
    '''
    self.origin=('none', 'none')

  @classmethod
  def from_histogram(cls, data, read_options):
    '''
    Create object from a histogram Nexus file.
    '''
    output=cls()
    output.read_options=read_options
    output._collect_info(data)

    output.proton_charge=data['proton_charge'].value[0]
    output.total_counts=data['total_counts'].value[0]
    output.tof_edges=data['bank1/time_of_flight'].value
    output.dangle=data['instrument/bank1/DANGLE/value'].value[0]
    output.dangle0=data['instrument/bank1/DANGLE0/value'].value[0]
    output.sangle=data['sample/SANGLE/value'].value[0]
    output.dpix=data['instrument/bank1/DIRPIX/value'].value[0]
    output.beam_width=data['instrument/aperture3/S3HWidth/value'].value[0]
    output.lambda_center=data['DASlogs/LambdaRequest/value'].value[0]
    # the data arrays
    output.data=data['bank1/data'].value.astype(float) # 3D dataset
    output.xydata=data['bank1']['data_x_y'].value.transpose().astype(float) # 2D dataset
    output.xtofdata=data['bank1']['data_x_time_of_flight'].value.astype(float) # 2D dataset
    return output

  @classmethod
  def from_event(cls, data, read_options):
    '''
    Load data from a Nexus file containing event information.
    Creates 3D histogram with ither linear or 1/t spaced 
    time of flight channels. The result has the same format as
    from the read_file function.
    '''
    output=cls()
    output.read_options=read_options
    bin_type=read_options['bin_type']
    bins=read_options['bins']
    output._collect_info(data)

    output.proton_charge=data['proton_charge'].value[0]
    output.total_counts=data['total_counts'].value[0]
    output.dangle=data['instrument/bank1/DANGLE/value'].value[0]
    output.dangle0=data['instrument/bank1/DANGLE0/value'].value[0]
    output.sangle=data['sample/SANGLE/value'].value[0]
    output.dpix=data['instrument/bank1/DIRPIX/value'].value[0]
    output.beam_width=data['instrument/aperture3/S3HWidth/value'].value[0]
    output.lambda_center=data['DASlogs/LambdaRequest/value'].value[0]

    # Histogram the data
    # create pixel map
    x=arange(304)
    y=arange(256)
    Y, X=meshgrid(y, x)
    X=X.flatten()
    Y=Y.flatten()
    # create ToF edges for the binning and correlate pixel indices with pixel position
    tof_ids=array(data['bank1_events/event_id'].value, dtype=int)
    tof_time=data['bank1_events/event_time_offset'].value
    tof_x=X[tof_ids]
    tof_y=Y[tof_ids]
    lcenter=data['DASlogs/LambdaRequest/value'].value[0]
    # ToF region for this specific central wavelength
    tmin=TOF_DISTANCE/H_OVER_M_NEUTRON*(lcenter-1.6)*1e-4
    tmax=TOF_DISTANCE/H_OVER_M_NEUTRON*(lcenter+1.6)*1e-4
    if bin_type.lower()=='linear':
      tof_edges=linspace(tmin, tmax, bins+1)
    elif bin_type.lower()=='1/x':
      tof_edges=1./linspace(1./tmin, 1./tmax, bins+1)
    else:
      raise ValueError, 'Unknown bin type %s'%bin_type

    # create the 3D binning
    Ixyt, D=histogramdd(vstack([tof_x, tof_y, tof_time]).transpose(),
                       bins=(arange(305)-0.5, arange(256)-0.5, tof_edges))
    # create projections for the 2D datasets
    Ixy=Ixyt.sum(axis=2)
    Ixt=Ixyt.sum(axis=1)
    # store the data
    output.tof_edges=D[2]
    output.data=Ixyt.astype(float) # 3D dataset
    output.xydata=Ixy.transpose().astype(float) # 2D dataset
    output.xtofdata=Ixt.astype(float) # 2D dataset
    return output

  def _collect_info(self, data):
    self.origin=(os.path.abspath(data.file.filename), data.name.lstrip('/'))

  def __repr__(self):
    return "<%s '%s' counts: %i>"%(self.__class__.__name__,
                                   "%s/%s"%(os.path.basename(self.origin[0]), self.origin[1]),
                                   self.total_counts)

  ################## Properties for easy data access ##########################
  @property
  def xdata(self): return self.xydata.mean(axis=0)

  @property
  def ydata(self): return self.xydata.mean(axis=1)

  @property
  def tofdata(self): return self.xtofdata.mean(axis=0)

  # coordinates corresponding to the data items
  @property
  def x(self): return arange(self.xydata.shape[1])

  @property
  def y(self): return arange(self.xydata.shape[0])

  @property
  def xy(self): return meshgrid(self.x, self.y)

  @property
  def tof(self): return (self.tof_edges[:-1]+self.tof_edges[1:])/2.

  @property
  def xtof(self): return meshgrid(self.tof, self.x)

  @property
  def lamda(self):
    v_n=TOF_DISTANCE/self.tof*1e6 #m/s
    lamda_n=H_OVER_M_NEUTRON/v_n*1e10 #A
    return lamda_n

  # easy access to automatically extracted reflectivity
  # could be useful for automatic extraction scripts
  @property
  def Q(self):
    if self._Q is None:
      self._autocalc_ref()
    return self._Q

  @property
  def I(self):
    if self._I is None:
      self._autocalc_ref()
    return self._I

  @property
  def dI(self):
    if self._dI is None:
      self._autocalc_ref()
    return self._dI

class Reflectivity(object):
  """
  Extraction of reflectivity from MRDatatset object storing all data
  and options used for the extraction process.
  """
  DEFAULT_OPTIONS=dict(
       x_pos=None,
       x_width=9,
       y_pos=102,
       y_width=204,
       bg_pos=80,
       bg_width=40,
       tth=None,
       dpix=None,
       scale=1.,
       extract_fan=False, # Treat every x-pixel separately and join the data afterwards
       normalization=None, # another Reflectivity object used for normalization
       scale_by_beam=True, # use the beam width in the scaling
       bg_method='data', # method to use for background subtraction
       P0=0,
       PN=0,
       number='0',
       )

  def __init__(self, dataset, **options):
    all_options=dict(Reflectivity.DEFAULT_OPTIONS)
    for key, value in options.items():
      if not key in all_options:
        raise ValueError, "%s is not a known option parameter"%key
      all_options[key]=value
    self.options=all_options
    self.origin=dataset.origin
    self.read_options=dataset.read_options
    if self.options['x_pos'] is None:
      # if nor x_pos is given, use the value from the dataset
      self.options['x_pos']=dataset.dpix-dataset.sangle/180.*pi/RAD_PER_PIX
    if self.options['tth'] is None:
      self.options['tth']=dataset.dangle-dataset.dangle0
    if self.options['dpix'] is None:
      self.options['dpix']=dataset.dpix
    self.lambda_center=dataset.lambda_center

    if all_options['extract_fan']:
      if all_options['normalization'] is None:
        raise ValueError, "Cannot extract fan reflectivity without normalization"
      self._calc_fan(dataset)
    else:
      self._calc_normal(dataset)

  def __repr__(self):
    output='<Reflectivity[%i] "%s/%s"'%(len(self.Q), os.path.basename(self.origin[0]),
                                        self.origin[1])
    if self.options['extract_fan']:
      output+=' FAN'
    if self.options['normalization'] is None:
      output+=' NOT normalized'
    output+='>'
    return output

  #############################################################################

  def _calc_normal(self, dataset):
    """
    Extract reflectivity from 3D dataset I(x,y,ToF).
    Uses a window in x and y to filter the 3D data and than sums all I values 
    for each ToF channel. Qz is calculated using the x window center position
    together with the tth-bank and direct pixel values. 
    Error is also calculated and all intermediate steps are stored in the object 
    (scaled and unscaled intensity and background).
    
    :param dataset: MRDataset object
    """
    tof_edges=dataset.tof_edges
    data=dataset.data
    x_pos=self.options['x_pos']
    x_width=self.options['x_width']
    y_pos=self.options['y_pos']
    y_width=self.options['y_width']
    scale=self.options['scale']/dataset.proton_charge # scale by user factor
    if self.options['scale_by_beam']:
      scale/=dataset.beam_width # scale by beam-size

    # Get regions in pixels as integers
    reg=map(lambda item: int(round(item)),
            [x_pos-x_width/2., x_pos+x_width/2.+1,
             y_pos-y_width/2., y_pos+y_width/2.+1])

    # restrict the intensity and background data to the given regions
    Idata=data[reg[0]:reg[1], reg[2]:reg[3], :]
    # calculate region size for later use
    size_I=float((reg[3]-reg[2])*(reg[1]-reg[0]))
    # calculate ROI intensities and normalize by number of points
    self.Iraw=Idata.sum(axis=0).sum(axis=0)
    self.I=self.Iraw/size_I*scale
    self.dIraw=sqrt(self.Iraw)
    self.dI=self.dIraw/size_I*scale

    self._calc_bg(dataset)

    # get incident angle of reflected beam
    relpix=self.options['dpix']-x_pos
    tth=(self.options['tth']*pi/180.+relpix*RAD_PER_PIX)
    self.ai=tth/2.
    # set good angular resolution as real resolution not implemented, yet
    dai=0.0001

    v_edges=TOF_DISTANCE/tof_edges*1e6 #m/s
    lamda_edges=H_OVER_M_NEUTRON/v_edges*1e10 #A
    # store the ToF as well for comparison etc.
    self.tof=(tof_edges[:-1]+tof_edges[1:])/2. # µs
    self.lamda=(lamda_edges[:-1]+lamda_edges[1:])/2.
    # resolution for lambda is digital range with equal probability
    # therefore it is the bin size divided by sqrt(12)
    self.dlamda=abs(lamda_edges[:-1]-lamda_edges[1:])/sqrt(12)

    # for reflectivity use Q as x
    self.Q=4.*pi/self.lamda*sin(self.ai)
    # error propagation from lambda and angular resolution
    self.dQ=4*pi*sqrt((self.dlamda/self.lamda**2*sin(self.ai))**2+
                      (cos(self.ai)*dai/self.lamda)**2)
    # finally scale reflectivity by the given factor and beam width
    self.R=(self.I-self.BG)
    self.dR=sqrt(self.dI**2+self.dBG**2)

    if self.options['normalization']:
      norm=self.options['normalization']
      idxs=norm.R>0.
      self.dR[idxs]=sqrt(
                   (self.dR[idxs]/norm.R[idxs])**2+
                   (self.R[idxs]/norm.R[idxs]**2*norm.dR[idxs])**2
                   )
      self.R[idxs]/=norm.R[idxs]
      self.R[logical_not(idxs)]=0.
      self.dR[logical_not(idxs)]=0.

  def _calc_fan(self, dataset):
    """
    Extract reflectivity from 4D dataset (x,y,ToF,I).
    Uses a window in x and y to filter the 4D data
    and than sums all I values for each ToF channel.
    
    In contrast to calc_reflectivity this function assumes
    that a brought region reflected from a bend sample is
    analyzed, so each x line corresponds to different alpha i
    values.
    """
    tof_edges=dataset.tof_edges
    data=dataset.data
    x_pos=self.options['x_pos']
    x_width=self.options['x_width']
    y_pos=self.options['y_pos']
    y_width=self.options['y_width']
    scale=self.options['scale']/dataset.proton_charge # scale by user factor
    if self.options['scale_by_beam']:
      scale/=dataset.beam_width # scale by beam-size

    reg=map(lambda item: int(round(item)),
            [x_pos-x_width/2., x_pos+x_width/2.+1,
             y_pos-y_width/2., y_pos+y_width/2.+1])

    Idata=data[reg[0]:reg[1], reg[2]:reg[3], :]
    x_region=arange(reg[0], reg[1])
    relpix=self.options['dpix']-x_region
    tth=(self.options['tth']*pi/180.+relpix*RAD_PER_PIX)
    ai=tth/2.
    self.ai=ai[len(ai)//2]

    v_edges=TOF_DISTANCE/tof_edges*1e6 #m/s
    lamda_edges=H_OVER_M_NEUTRON/v_edges*1e10 #A
    self.tof=(tof_edges[:-1]+tof_edges[1:])/2. # µs
    self.lamda=(lamda_edges[:-1]+lamda_edges[1:])/2.
    # resolution for lambda is digital range with equal probability
    # therefore it is the bin size divided by sqrt(12)
    self.dlamda=abs(lamda_edges[:-1]-lamda_edges[1:])/sqrt(12)

    # calculate ROI intensities and normalize by number of points
    # still keeping it as 2D dataset
    self.Iraw=Idata.sum(axis=1)
    I=self.Iraw/(reg[3]-reg[2])*scale
    self.dIraw=sqrt(self.Iraw)
    dI=self.dIraw/(reg[3]-reg[2])*scale
    # For comparison store intensity summed over whole area
    self.I=I.sum(axis=0)/(reg[1]-reg[0])
    self.dI=dI.sum(axis=0)/(reg[1]-reg[0])

    self._calc_bg(dataset)

    R=(I-self.BG[newaxis, :])
    dR=sqrt(dI**2+(self.dBG**2)[newaxis, :])

    norm=self.options['normalization']
    normR=where(norm.R>0, norm.R, 1.)
    # normalize each line by the incident intensity including error propagation
    dR=sqrt((dR/normR[newaxis, :])**2+(R*(norm.dR/normR**2)[newaxis, :])**2)
    R/=normR[newaxis, :]
    # reduce ToF region to points with incident intensity

    # calculate Q for each point of R
    Qz_edges=4.*pi/lamda_edges*sin(ai)[:, newaxis]
    Qz_centers=(Qz_edges[:, :-1]+Qz_edges[:, 1:])/2.
    #dQz=abs(Qz_edges[:, :-1]-Qz_edges[:, 1:])/2. #sqrt(12) error due to binning

    # create the Q bins to combine all R lines to
    # uses the smallest and largest Q all lines have in common with
    # a step size which has one point of every line in it.
    #Qz_start=Qz_edges[0,-1]
    Qz_start=Qz_edges[0, where(norm.R>0)[0][-1]]
    Qz_end=Qz_edges[-1, where(norm.R>0)[0][0]]
    Q=[]
    dQ=[]
    Rsum=[]
    ddRsum=[]
    Qz_edges_first=Qz_edges[0]
    Qz_edges_last=Qz_edges[-1]
    lines=range(Qz_edges.shape[0])
    ddR=dR**2
    for Qz_bin_low in reversed(Qz_edges_first[(Qz_edges_first<=Qz_end)&(Qz_edges_first>=Qz_start)]):
      # create a bin where at least one point from every
      # line is present
      try:
        # at least one point at the end can't be made into a bin this way
        Qz_bin_high=Qz_edges_last[Qz_edges_last>=Qz_bin_low][-2]
      except IndexError:
        break
      Q.append((Qz_bin_high+Qz_bin_low)/2.)
      # error is assumed to be dominated by the large binning
      dQ.append((Qz_bin_high-Qz_bin_low)/sqrt(12.))
      Rsumi=[]
      ddRsumi=[]
      for line in lines:
        # each line is treated equally in weight but there can be more than
        # one point per line in the same bin, so these are averaged
        select=(Qz_centers[line]>=Qz_bin_low)&(Qz_centers[line]<=Qz_bin_high)
        Rselect=R[line, select]
        ddRselect=ddR[line, select]
        Rsumi.append(Rselect.sum()/len(Rselect))
        ddRsumi.append(ddRselect.sum()/len(Rselect)**2)
      Rsum.append(array(Rsumi).sum())
      ddRsum.append(array(ddRsumi).sum())

    # sort the lists according to the default order from normal readout
    # and store them as numpy arrays
    Q.reverse()
    dQ.reverse()
    Rsum.reverse()
    ddRsum.reverse()
    self.dQ=array(dQ)
    self.Q=array(Q)
    self.R=array(Rsum)/len(lines)
    self.dR=sqrt(array(ddRsum))/len(lines)

  def _calc_bg(self, dataset):
    '''
    Calculate the background intensity vs. ToF.
    Equal for normal and fan reflectivity extraction.
    
    Methods supported:
        'data': Just take a region in x to extract an average count rate vs. ToF
    '''
    if self.options['bg_method']=='data':
      data=dataset.data
      y_pos=self.options['y_pos']
      y_width=self.options['y_width']
      bg_pos=self.options['bg_pos']
      bg_width=self.options['bg_width']
      scale=self.options['scale']/dataset.proton_charge # scale by user factor
      if self.options['scale_by_beam']:
        scale/=dataset.beam_width # scale by beam-size

      # Get regions in pixels as integers
      reg=map(lambda item: int(round(item)),
              [bg_pos-bg_width/2., bg_pos+bg_width/2.+1,
               y_pos-y_width/2., y_pos+y_width/2.+1 ])

      # restrict the intensity and background data to the given regions
      bgdata=data[reg[0]:reg[1], reg[2]:reg[3], :]
      # calculate region size for later use
      size_BG=float((reg[3]-reg[2])*(reg[1]-reg[0]))
      # calculate ROI intensities and normalize by number of points
      self.BGraw=bgdata.sum(axis=0).sum(axis=0)
      self.BG=self.BGraw/size_BG*scale
      self.dBGraw=sqrt(self.BGraw)
      self.dBG=self.dBGraw/size_BG*scale
    else:
      raise ValueError, "Unknown background method '%s'"%self.options['bg_method']

class OffSpecular(Reflectivity):
  '''
    Calculate off-specular scattering similarly as done for reflectivity.
  '''

  def __init__(self, dataset, **options):
    all_options=dict(OffSpecular.DEFAULT_OPTIONS)
    for key, value in options.items():
      if not key in all_options:
        raise ValueError, "%s is not a known option parameter"%key
      all_options[key]=value
    self.options=all_options
    self.origin=dataset.origin
    self.read_options=dataset.read_options
    if self.options['x_pos'] is None:
      # if nor x_pos is given, use the value from the dataset
      self.options['x_pos']=dataset.dpix-dataset.sangle/180.*pi/RAD_PER_PIX
    if self.options['tth'] is None:
      self.options['tth']=dataset.dangle-dataset.dangle0
    if self.options['dpix'] is None:
      self.options['dpix']=dataset.dpix
    self.lambda_center=dataset.lambda_center

    self._calc_offspec(dataset)

  def __repr__(self):
    output='<OffSpecular[%i] "%s/%s"'%(len(self.Q), os.path.basename(self.origin[0]),
                                        self.origin[1])
    if self.options['normalization'] is None:
      output+=' NOT normalized'
    output+='>'
    return output

  def _calc_offspec(self, dataset):
    """
      Extract off-specular scattering from 4D dataset (x,y,ToF,I).
      Uses a window in y to filter the 4D data
      and than sums all I values for each ToF and x channel.
      Qz,Qx,kiz,kfz is calculated using the x and ToF positions
      together with the tth-bank and direct pixel values.
    """
    tof_edges=dataset.tof_edges
    data=dataset.data
    x_pos=self.options['x_pos']
    x_width=self.options['x_width']
    y_pos=self.options['y_pos']
    y_width=self.options['y_width']
    scale=self.options['scale']/dataset.proton_charge # scale by user factor
    if self.options['scale_by_beam']:
      scale/=dataset.beam_width # scale by beam-size

    # Get regions in pixels as integers
    reg=map(lambda item: int(round(item)),
            [x_pos-x_width/2., x_pos+x_width/2.+1,
             y_pos-y_width/2., y_pos+y_width/2.+1])

    self._calc_bg(dataset)

    xtth=self.options['dpix']-arange(data.shape[0])[DETECTOR_X_REGION[0]:DETECTOR_X_REGION[1]]
    pix_offset_spec=self.options['dpix']-x_pos
    tth_spec=self.options['tth']*pi/180.+pix_offset_spec*RAD_PER_PIX
    af=self.options['tth']*pi/180.+xtth*RAD_PER_PIX-tth_spec/2.
    ai=ones_like(af)*tth_spec/2.

    v_edges=TOF_DISTANCE/tof_edges*1e6 #m/s
    lamda_edges=H_OVER_M_NEUTRON/v_edges*1e10 #A
    # store the ToF as well for comparison etc.
    self.tof=(tof_edges[:-1]+tof_edges[1:])/2. # µs
    self.lamda=(lamda_edges[:-1]+lamda_edges[1:])/2.
    # resolution for lambda is digital range with equal probability
    # therefore it is the bin size divided by sqrt(12)
    self.dlamda=abs(lamda_edges[:-1]-lamda_edges[1:])/sqrt(12)
    k=2.*pi/self.lamda

    # calculate reciprocal space, incident and outgoing perpendicular wave vectors
    self.Qz=k[newaxis, :]*(sin(af)+sin(ai))[:, newaxis]
    self.Qx=k[newaxis, :]*(cos(af)-cos(ai))[:, newaxis]
    self.ki_z=k[newaxis, :]*sin(ai)[:, newaxis]
    self.kf_z=k[newaxis, :]*sin(af)[:, newaxis]

    # calculate ROI intensities and normalize by number of points
    Idata=data[DETECTOR_X_REGION[0]:DETECTOR_X_REGION[1], reg[2]:reg[3], :]
    self.Iraw=Idata.sum(axis=1)
    self.dIraw=sqrt(self.Iraw)
    # normalize data by width in y and multiply scaling factor
    self.I=self.Iraw/(reg[3]-reg[2])*scale
    self.dI=self.dIraw/(reg[3]-reg[2])*scale
    self.S=self.I-self.BG[newaxis, :]
    self.dS=sqrt(self.dI**2+(self.dBG**2)[newaxis, :])

    if self.options['normalization']:
      norm=self.options['normalization']
      idxs=norm.R>0.
      self.dS[:, idxs]=sqrt(
                   (self.dS[:, idxs]/norm.R[idxs][newaxis, :])**2+
                   (self.S[:, idxs]/norm.R[idxs][newaxis, :]**2*norm.dR[idxs][newaxis, :])**2
                   )
      self.S[:, idxs]/=norm.R[idxs][newaxis, :]
      self.S[:, logical_not(idxs)]=0.
      self.dS[:, logical_not(idxs)]=0.

def smooth_data(settings, x, y, I, sigmas=3., callback=None):
  '''
    Smooth a irregular spaced dataset onto a regular grid.
    Takes each intensities with a distance < 3*sigma
    to a given grid point and averages their intensities
    weighted by the gaussian of the distance.
  '''
  gridx, gridy=settings['grid']
  sigmax, sigmay=settings['sigma']
  ssigmax, ssigmay=sigmax**2, sigmay**2
  x1, x2, y1, y2=settings['region']
  xout=linspace(x1, x2, gridx)
  yout=linspace(y1, y2, gridy)
  Xout, Yout=meshgrid(xout, yout)
  Iout=zeros_like(Xout)
  imax=len(Xout)
  for i in range(imax):
    if callback is not None and i%5==0:
      progress=float(i)/imax
      callback(progress)
    for j in range(len(Xout[0])):
      xij=Xout[i, j]
      yij=Yout[i, j]
      rij=(x-xij)**2/ssigmax+(y-yij)**2/ssigmay # normalized distance^2
      take=where(rij<sigmas**2) # take points up to 3 sigma distance
      Pij=exp(-0.5*rij[take])
      Pij/=Pij.sum()
      Iout[i, j]=(Pij*I[take]).sum()
  return Xout, Yout, Iout
