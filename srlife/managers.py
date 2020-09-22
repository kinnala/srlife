"""
  Solution managers actually walk a model through all the steps to solve
"""

import tqdm

import multiprocess
import itertools

from srlife import solverparams

class SolutionManager:
  """
    High level solution manager walking through the thermal, structural,
    and damage calculations
  """
  def __init__(self, receiver, thermal_solver, thermal_material,
      fluid_material, structural_solver, deformation_material,
      damage_material, system_solver, damage_model,
      pset = solverparams.ParameterSet()):
    """
      Parameters:
        receiver                receiver object to solve
        thermal_solver          how to solve the heat transport
        thermal_material        solid thermal properties
        fluid_material          fluid thermal properties
        structural_solver       how to solve the mechanics problem
        deformation_material    how things deform with time
        damage_material         how to calculate creep damage
        system_solver           how to tie tubes into the structural system
        damage_model            how to calculate damage from the results

      Additional Parameters:
        pset                    optional set of solver parameters
    """
    self.receiver = receiver
    self.thermal_solver = thermal_solver
    self.thermal_material = thermal_material
    self.fluid_material = fluid_material
    self.structural_solver = structural_solver
    self.deformation_material = deformation_material
    self.damage_material = damage_material
    self.system_solver = system_solver
    self.damage_model = damage_model

    self.pset = pset
    self.nthreads = pset.get_default("nthreads", 1)
    self.progress = pset.get_default("progress_bars", False)

  @property
  def tubes(self):
    """
      Direct iterator over tubes
    """
    return self.receiver.tubes

  @property
  def ntubes(self):
    return len(list(self.tubes))
  
  def progress_decorator(self, base, ntotal):
    """
      Either wrap with a progress bar decorator or not

      Parameters:
        base            base function to wrap
        ntotal          total number in iterator, needed for wrapping
                        iterators
    """
    if self.progress:
      return tqdm.tqdm(base, total = ntotal)
    else:
      return base

  def solve_life(self):
    """
      The trigger for everything: solve the complete problem and report the
      best-estimate life
    """
    self.solve_heat_transfer()
    self.solve_structural()

    return self.calculate_damage()

  def calculate_damage(self):
    """
      Calculate damage from the results
    """
    if self.progress:
      print("Calculating damage:")
    return self.damage_model.determine_life(self.receiver, self.damage_material, 
        nthreads = self.nthreads, decorator = self.progress_decorator)

  def solve_heat_transfer(self):
    """
      Solve the heat transfer problem for each tube
    """
    if self.progress:
      print("Running thermal analysis:")
    with multiprocess.Pool(self.nthreads) as p:
      temps = list(
          self.progress_decorator(
          p.imap(lambda x: self.thermal_solver.solve(x, self.thermal_material, self.fluid_material),
        self.tubes), self.ntubes)
          )
    for tube, temps in zip(self.tubes, temps):
      tube.add_results("temperature", temps)

  def solve_structural(self):
    """
      Solve the structural problem for the complete system
    """
    if self.progress:
      print("Running structural analysis:")
    self.system_solver.solve(self.receiver, self.deformation_material,
        self.structural_solver, nthreads = self.nthreads, 
        decorator = self.progress_decorator, verbose = self.progress)
